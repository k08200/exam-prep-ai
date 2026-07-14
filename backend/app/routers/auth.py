import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.course import Course
from app.models.analysis import ProfessorAnalysis
from app.models.exam import ConceptTracking, Exam, ExamQuestion, StudentResponse
from app.models.material import Material
from app.models.user import User
from app.schemas.auth import AIUsageResponse, Token, UserCreate, UserResponse, UserUpdate, PasswordChange
from app.services.ai_usage_service import AIUsageService

router = APIRouter(prefix="/auth", tags=["auth"])
_failed_login_attempts: dict[str, list[float]] = {}
ai_usage_service = AIUsageService()


def _normalize_email(email: str) -> str:
    """Use one canonical form for login, registration, and token lookup."""
    return email.strip().lower()


def _prune_login_attempts(email: str, now: float) -> list[float]:
    cutoff = now - settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    attempts = [
        ts for ts in _failed_login_attempts.get(email, [])
        if ts >= cutoff
    ]
    if attempts:
        _failed_login_attempts[email] = attempts
    else:
        _failed_login_attempts.pop(email, None)
    return attempts


def _record_failed_login(email: str, now: float) -> None:
    attempts = _prune_login_attempts(email, now)
    attempts.append(now)
    _failed_login_attempts[email] = attempts


def _clear_failed_logins(email: str | None = None) -> None:
    if email is None:
        _failed_login_attempts.clear()
    else:
        _failed_login_attempts.pop(email, None)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user account."""
    email = _normalize_email(str(user_in.email))
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    new_user = User(
        email=email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate a user and return a JWT access token."""
    email = _normalize_email(form_data.username)
    now = time.monotonic()
    if len(_prune_login_attempts(email, now)) >= settings.AUTH_RATE_LIMIT_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        _record_failed_login(email, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    _clear_failed_logins(email)
    access_token = create_access_token(data={"sub": user.email, "ver": user.token_version})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.get("/me/ai-usage", response_model=AIUsageResponse)
async def get_ai_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIUsageResponse:
    """Return today's reserved AI work and the configured account limits."""
    usage = await ai_usage_service.get_snapshot(db, current_user.id)
    return AIUsageResponse(
        usage_date=usage.usage_date,
        analyses_used=usage.analyses_used,
        analyses_limit=settings.MAX_DAILY_AI_ANALYSES,
        questions_generated=usage.questions_generated,
        questions_limit=settings.MAX_DAILY_AI_GENERATED_QUESTIONS,
        responses_graded=usage.responses_graded,
        grades_limit=settings.MAX_DAILY_AI_GRADES,
    )


@router.get("/me/export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Download a portable JSON archive of the current user's study data."""
    courses_result = await db.execute(
        select(Course)
        .where(Course.user_id == current_user.id)
        .order_by(Course.created_at.asc())
    )
    courses = courses_result.scalars().all()
    course_exports = {
        course.id: {
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "professor_name": course.professor_name,
            "subject": course.subject,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "materials": [],
            "analysis": None,
            "exams": [],
            "concept_tracking": [],
        }
        for course in courses
    }

    materials_result = await db.execute(
        select(Material)
        .join(Course, Material.course_id == Course.id)
        .where(Course.user_id == current_user.id)
        .order_by(Material.created_at.asc())
    )
    for material in materials_result.scalars().all():
        course_exports[material.course_id]["materials"].append(
            {
                "id": material.id,
                "original_filename": material.original_filename,
                "file_type": material.file_type,
                "file_size": material.file_size,
                "extracted_text": material.extracted_text,
                "page_count": material.page_count,
                "processing_status": material.processing_status,
                "processing_error": material.processing_error,
                "created_at": material.created_at,
            }
        )

    analyses_result = await db.execute(
        select(ProfessorAnalysis)
        .join(Course, ProfessorAnalysis.course_id == Course.id)
        .where(Course.user_id == current_user.id)
    )
    for analysis in analyses_result.scalars().all():
        course_exports[analysis.course_id]["analysis"] = {
            "id": analysis.id,
            "top_concepts": analysis.top_concepts,
            "question_types": analysis.question_types,
            "topic_distribution": analysis.topic_distribution,
            "professor_terms": analysis.professor_terms,
            "exam_patterns": analysis.exam_patterns,
            "raw_analysis": analysis.raw_analysis,
            "thinking_tokens_used": analysis.thinking_tokens_used,
            "total_tokens_used": analysis.total_tokens_used,
            "created_at": analysis.created_at,
            "updated_at": analysis.updated_at,
        }

    exams_result = await db.execute(
        select(Exam)
        .where(Exam.user_id == current_user.id)
        .order_by(Exam.created_at.asc())
    )
    exam_exports: dict[object, dict] = {}
    for exam in exams_result.scalars().all():
        exported_exam = {
            "id": exam.id,
            "title": exam.title,
            "mode": exam.mode,
            "question_count": exam.question_count,
            "status": exam.status,
            "score": exam.score,
            "total_tokens_used": exam.total_tokens_used,
            "created_at": exam.created_at,
            "updated_at": exam.updated_at,
            "completed_at": exam.completed_at,
            "questions": [],
            "responses": [],
        }
        course_exports[exam.course_id]["exams"].append(exported_exam)
        exam_exports[exam.id] = exported_exam

    questions_result = await db.execute(
        select(ExamQuestion)
        .join(Exam, ExamQuestion.exam_id == Exam.id)
        .where(Exam.user_id == current_user.id)
        .order_by(ExamQuestion.question_number.asc())
    )
    for question in questions_result.scalars().all():
        exam_exports[question.exam_id]["questions"].append(
            {
                "id": question.id,
                "question_number": question.question_number,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "choices": question.choices,
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
                "concepts": question.concepts,
                "difficulty": question.difficulty,
                "tokens_used": question.tokens_used,
            }
        )

    responses_result = await db.execute(
        select(StudentResponse)
        .join(Exam, StudentResponse.exam_id == Exam.id)
        .where(
            StudentResponse.user_id == current_user.id,
            Exam.user_id == current_user.id,
        )
        .order_by(StudentResponse.created_at.asc())
    )
    for response in responses_result.scalars().all():
        exam_exports[response.exam_id]["responses"].append(
            {
                "id": response.id,
                "question_id": response.question_id,
                "student_answer": response.student_answer,
                "is_correct": response.is_correct,
                "score": response.score,
                "ai_feedback": response.ai_feedback,
                "created_at": response.created_at,
            }
        )

    concepts_result = await db.execute(
        select(ConceptTracking)
        .where(ConceptTracking.user_id == current_user.id)
        .order_by(ConceptTracking.course_id, ConceptTracking.concept)
    )
    for concept in concepts_result.scalars().all():
        course = course_exports.get(concept.course_id)
        if course is not None:
            course["concept_tracking"].append(
                {
                    "concept": concept.concept,
                    "attempts": concept.attempts,
                    "correct_count": concept.correct_count,
                    "incorrect_count": concept.incorrect_count,
                    "weakness_score": concept.weakness_score,
                    "last_attempted": concept.last_attempted,
                    "updated_at": concept.updated_at,
                }
            )

    payload = {
        "format": "exam-prep-ai-user-export",
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc),
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "created_at": current_user.created_at,
        },
        "courses": list(course_exports.values()),
    }
    filename = f"exam-prep-ai-export-{int(time.time())}.json"
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the current user's profile fields."""
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the current user's password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.token_version += 1
    await db.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete the current user and all their data."""
    result = await db.execute(
        select(Material.file_path)
        .join(Course, Material.course_id == Course.id)
        .where(Course.user_id == current_user.id)
    )
    for file_path in result.scalars().all():
        Path(file_path).unlink(missing_ok=True)

    await db.delete(current_user)
    await db.commit()
