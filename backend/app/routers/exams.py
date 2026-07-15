import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user
from app.core.sse import iter_with_heartbeat
from app.models.analysis import ProfessorAnalysis
from app.models.course import Course
from app.models.exam import (
    ConceptTracking,
    Exam,
    ExamQuestion,
    StudentResponse,
    EXAM_STATUS_ACTIVE,
    EXAM_STATUS_COMPLETED,
    EXAM_STATUS_DRAFT,
)
from app.models.user import User
from app.schemas.exam import (
    ConceptHeatmapItem,
    ExamCreate,
    ExamDetailResponse,
    ExamResponse,
    ExamResult,
    ExamSubmit,
    GeneratedQuestion,
    GradeResponse,
    MultipleChoiceOption,
    QuestionResponse,
    QuestionResult,
)
from app.services.analytics_service import AnalyticsService
from app.services import AIServiceProxy
from app.services.ai_usage_service import AIUsageService

router = APIRouter(tags=["exams"])
claude_service = AIServiceProxy()
analytics_service = AnalyticsService()
_exam_generation_course_locks: set[uuid.UUID] = set()
logger = logging.getLogger(__name__)
ai_usage_service = AIUsageService()


async def mark_stale_draft_exams(
    db: AsyncSession,
    course_id: uuid.UUID | None = None,
) -> int:
    """Remove draft exams left behind by a crashed generation stream."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.EXAM_GENERATION_STALE_MINUTES
    )
    query = select(Exam).where(
        Exam.status == EXAM_STATUS_DRAFT,
        Exam.created_at < cutoff,
    )
    if course_id is not None:
        query = query.where(Exam.course_id == course_id)

    result = await db.execute(query)
    stale_exams = result.scalars().all()
    for exam in stale_exams:
        await db.delete(exam)
    if stale_exams:
        await db.flush()
    return len(stale_exams)


async def recover_stale_exam_generations() -> int:
    """Startup recovery hook for drafts orphaned by a process restart."""
    async with AsyncSessionLocal() as db:
        count = await mark_stale_draft_exams(db)
        if count:
            await db.commit()
        return count


async def _assert_course_ownership(
    course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Course:
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return course


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _question_to_schema(q: ExamQuestion) -> QuestionResponse:
    choices = None
    if q.choices:
        choices = [MultipleChoiceOption(**c) for c in q.choices]
    return QuestionResponse(
        id=q.id,
        question_number=q.question_number,
        question_text=q.question_text,
        question_type=q.question_type,
        choices=choices,
        difficulty=q.difficulty,
        concepts=q.concepts or [],
    )


async def _discard_draft_exam(db: AsyncSession, exam_id: uuid.UUID) -> None:
    """Remove an unfinished draft exam after generation fails or is cancelled."""
    await db.rollback()
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    draft = result.scalar_one_or_none()
    if draft is not None and draft.status == EXAM_STATUS_DRAFT:
        await db.delete(draft)
        await db.commit()


async def _stream_exam_generation(
    exam_id: uuid.UUID,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_name: str,
    analysis_data: dict,
    exam_create: ExamCreate,
    lock_course_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    """Stream question generation via SSE, persisting each question as it arrives."""
    try:
        async with AsyncSessionLocal() as db:
            async for event in _stream_exam_generation_with_session(
                db=db,
                exam_id=exam_id,
                user_id=user_id,
                course_id=course_id,
                course_name=course_name,
                analysis_data=analysis_data,
                exam_create=exam_create,
            ):
                yield event
    finally:
        _exam_generation_course_locks.discard(lock_course_id)


async def _stream_exam_generation_with_session(
    db: AsyncSession,
    exam_id: uuid.UUID,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_name: str,
    analysis_data: dict,
    exam_create: ExamCreate,
) -> AsyncGenerator[str, None]:
    """Run exam generation against a session owned by the stream lifecycle."""
    total_tokens = 0
    question_number = 1

    try:
        # Determine topics for cram mode
        topics = exam_create.topics
        if exam_create.mode == "cram" and not topics:
            user_concepts_result = await db.execute(
                select(ConceptTracking).where(
                    ConceptTracking.user_id == user_id,
                    ConceptTracking.course_id == course_id,
                ).order_by(ConceptTracking.weakness_score.desc())
            )
            user_concepts = [
                {"concept": ct.concept, "weakness_score": ct.weakness_score}
                for ct in user_concepts_result.scalars().all()
            ]
            topics = await analytics_service.get_cram_topics(
                analysis={
                    "top_concepts": analysis_data["top_concepts"],
                    "topic_distribution": analysis_data["topic_distribution"],
                },
                user_concepts=user_concepts,
            )

        try:
            yield _sse_event({"type": "heartbeat"})
            async for event in iter_with_heartbeat(
                claude_service.generate_exam_questions(
                    course_name=course_name,
                    analysis=analysis_data,
                    question_count=exam_create.question_count,
                    mode=exam_create.mode,
                    topics=topics,
                )
            ):
                event_type = event.get("type")

                if event_type == "heartbeat":
                    yield _sse_event(event)
                elif event_type == "error":
                    await _discard_draft_exam(db, exam_id)
                    yield _sse_event(event)
                    return
                elif event_type == "question":
                    try:
                        q_data = GeneratedQuestion.model_validate(event.get("question"))
                        tokens = max(int(event.get("tokens", 0)), 0)
                    except (ValidationError, TypeError, ValueError) as exc:
                        logger.warning(
                            "invalid_generated_question",
                            extra={"exam_id": str(exam_id), "error": str(exc)},
                        )
                        await _discard_draft_exam(db, exam_id)
                        yield _sse_event(
                            {
                                "type": "error",
                                "content": "AI returned an invalid exam question. Please try again.",
                                "retryable": True,
                            }
                        )
                        return
                    total_tokens += tokens

                    question = ExamQuestion(
                        exam_id=exam_id,
                        question_number=question_number,
                        question_text=q_data.question_text,
                        question_type=q_data.question_type,
                        choices=[choice.model_dump() for choice in q_data.choices] if q_data.choices else None,
                        correct_answer=q_data.correct_answer,
                        explanation=q_data.explanation,
                        concepts=q_data.concepts,
                        difficulty=q_data.difficulty,
                        tokens_used=tokens,
                    )
                    db.add(question)
                    await db.flush()
                    await db.refresh(question)

                    question_number += 1

                    yield _sse_event(
                        {
                            "type": "question",
                            "question": {
                                "id": str(question.id),
                                "question_number": question.question_number,
                                "question_text": question.question_text,
                                "question_type": question.question_type,
                                "choices": question.choices,
                                "difficulty": question.difficulty,
                                "concepts": question.concepts,
                            },
                            "tokens_used": tokens,
                        }
                    )

                elif event_type == "complete":
                    total_tokens = event.get("tokens", total_tokens)

        except Exception as exc:
            await _discard_draft_exam(db, exam_id)
            yield _sse_event({"type": "error", "content": str(exc), "retryable": True})
            return

        generated_count = question_number - 1
        if generated_count != exam_create.question_count:
            await _discard_draft_exam(db, exam_id)
            yield _sse_event(
                {
                    "type": "error",
                    "content": (
                        "Exam generation failed: expected "
                        f"{exam_create.question_count} questions, got {generated_count}."
                    ),
                    "retryable": True,
                }
            )
            return

        # Finalize exam record
        result = await db.execute(select(Exam).where(Exam.id == exam_id))
        managed_exam = result.scalar_one_or_none()
        if managed_exam is None:
            await db.rollback()
            yield _sse_event(
                {
                    "type": "error",
                    "content": "Exam generation failed: draft exam no longer exists.",
                    "retryable": True,
                }
            )
            return
        managed_exam.status = EXAM_STATUS_ACTIVE
        managed_exam.total_tokens_used = total_tokens
        await db.commit()

        yield _sse_event(
            {
                "type": "complete",
                "exam_id": str(managed_exam.id),
                "total_tokens": total_tokens,
                "question_count": question_number - 1,
            }
        )
    except asyncio.CancelledError:
        await _discard_draft_exam(db, exam_id)
        raise


@router.get("/exams", response_model=list[ExamResponse])
async def list_all_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ExamResponse]:
    """Return the most recent exams across all courses for the current user."""
    result = await db.execute(
        select(Exam)
        .where(Exam.user_id == current_user.id)
        .order_by(Exam.created_at.desc())
        .limit(limit)
    )
    return [ExamResponse.model_validate(e) for e in result.scalars().all()]


@router.post("/courses/{course_id}/exams")
async def create_exam(
    course_id: uuid.UUID,
    exam_create: ExamCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Create an exam and stream question generation via SSE.
    Requires a completed professor analysis for the course.
    """
    course = await _assert_course_ownership(course_id, current_user.id, db)

    analysis_result = await db.execute(
        select(ProfessorAnalysis).where(ProfessorAnalysis.course_id == course_id)
    )
    analysis = analysis_result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Professor analysis not found. Run POST /courses/{course_id}/analysis first.",
        )

    await mark_stale_draft_exams(db, course_id=course_id)

    if course_id in _exam_generation_course_locks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam generation is already running for this course.",
        )

    existing_draft_result = await db.execute(
        select(Exam.id).where(
            Exam.course_id == course_id,
            Exam.status == EXAM_STATUS_DRAFT,
        )
    )
    if existing_draft_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam generation is already running for this course.",
        )

    _exam_generation_course_locks.add(course_id)
    course_name = course.name
    user_id = current_user.id
    analysis_data = {
        "top_concepts": analysis.top_concepts,
        "question_types": analysis.question_types,
        "topic_distribution": analysis.topic_distribution,
        "professor_terms": analysis.professor_terms,
        "exam_patterns": analysis.exam_patterns,
    }

    try:
        await ai_usage_service.reserve(
            db,
            current_user.id,
            questions=exam_create.question_count,
        )
        exam = Exam(
            course_id=course_id,
            user_id=user_id,
            title=exam_create.title,
            mode=exam_create.mode,
            question_count=exam_create.question_count,
            status=EXAM_STATUS_DRAFT,
        )
        db.add(exam)
        await db.flush()
        await db.refresh(exam)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        _exam_generation_course_locks.discard(course_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam generation is already running for this course.",
        ) from exc
    except Exception:
        _exam_generation_course_locks.discard(course_id)
        raise

    return StreamingResponse(
        _stream_exam_generation(
            exam_id=exam.id,
            user_id=user_id,
            course_id=course_id,
            course_name=course_name,
            analysis_data=analysis_data,
            exam_create=exam_create,
            lock_course_id=course_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/courses/{course_id}/exams", response_model=list[ExamResponse])
async def list_exams(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExamResponse]:
    """Return all exams for a course."""
    await _assert_course_ownership(course_id, current_user.id, db)
    result = await db.execute(
        select(Exam)
        .where(Exam.course_id == course_id, Exam.user_id == current_user.id)
        .order_by(Exam.created_at.desc())
    )
    exams = result.scalars().all()
    return [ExamResponse.model_validate(e) for e in exams]


@router.get("/exams/{exam_id}", response_model=ExamDetailResponse)
async def get_exam(
    exam_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamDetailResponse:
    """Return an exam with all questions (answers hidden)."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if exam.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    questions_result = await db.execute(
        select(ExamQuestion)
        .where(ExamQuestion.exam_id == exam_id)
        .order_by(ExamQuestion.question_number)
    )
    questions = questions_result.scalars().all()

    return ExamDetailResponse(
        id=exam.id,
        course_id=exam.course_id,
        title=exam.title,
        mode=exam.mode,
        question_count=exam.question_count,
        status=exam.status,
        score=exam.score,
        total_tokens_used=exam.total_tokens_used,
        created_at=exam.created_at,
        questions=[_question_to_schema(q) for q in questions],
    )


@router.get("/exams/{exam_id}/result", response_model=ExamResult)
async def get_exam_result(
    exam_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamResult:
    """Return persisted grading results for a completed exam."""
    result = await db.execute(
        select(Exam)
        .where(Exam.id == exam_id)
        .options(selectinload(Exam.student_responses).selectinload(StudentResponse.question))
    )
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if exam.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if exam.status != EXAM_STATUS_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam has not been submitted yet",
        )

    responses = sorted(
        exam.student_responses,
        key=lambda response: response.question.question_number,
    )

    return ExamResult(
        exam_id=exam.id,
        score=exam.score or 0.0,
        total_questions=len(responses),
        correct_count=sum(1 for response in responses if response.is_correct),
        results=[
            QuestionResult(
                question_id=response.question_id,
                question_number=response.question.question_number,
                is_correct=bool(response.is_correct),
                score=response.score or 0.0,
                student_answer=response.student_answer,
                correct_answer=response.question.correct_answer,
                ai_feedback=response.ai_feedback or "",
                concepts=response.question.concepts or [],
            )
            for response in responses
        ],
        total_tokens_used=exam.total_tokens_used,
    )


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete one exam and its associated questions/responses."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if exam.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await db.delete(exam)
    await db.commit()


@router.post("/exams/{exam_id}/submit", response_model=ExamResult)
async def submit_exam(
    exam_id: uuid.UUID,
    submission: ExamSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamResult:
    """Grade all student answers and return detailed results."""
    # Serialize submissions for one exam so a retry cannot grade it twice.
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id).with_for_update()
    )
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if exam.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if exam.status == EXAM_STATUS_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam already submitted",
        )
    if exam.status != EXAM_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam is not ready to submit",
        )

    # Load all questions indexed by ID
    questions_result = await db.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    )
    questions_by_id = {q.id: q for q in questions_result.scalars().all()}
    if not questions_by_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam has no questions to grade",
        )

    submitted_question_ids = [answer.question_id for answer in submission.answers]
    if len(submitted_question_ids) != len(set(submitted_question_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate answers for the same question are not allowed",
        )

    unknown_question_ids = set(submitted_question_ids) - set(questions_by_id)
    if unknown_question_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Submitted answers include questions that do not belong to this exam",
        )

    await ai_usage_service.reserve(
        db,
        current_user.id,
        grades=len(questions_by_id),
    )

    # Fetch existing professor analysis for grading context
    analysis_result = await db.execute(
        select(ProfessorAnalysis).where(ProfessorAnalysis.course_id == exam.course_id)
    )
    analysis = analysis_result.scalar_one_or_none()
    professor_context = ""
    if analysis and analysis.professor_terms:
        professor_context = ", ".join(t["term"] for t in analysis.professor_terms[:20])

    results: list[QuestionResult] = []
    grading_tokens = 0
    correct_count = 0

    # Build a map of submitted answers
    answers_map = {a.question_id: a.student_answer.strip() for a in submission.answers}

    for question in sorted(questions_by_id.values(), key=lambda q: q.question_number):
        student_answer = answers_map.get(question.id, "")

        # Validate every provider response before mutating grading state.
        try:
            grade = GradeResponse.model_validate(
                await claude_service.grade_response(
                    question={
                        "question_text": question.question_text,
                        "question_type": question.question_type,
                        "choices": question.choices,
                        "correct_answer": question.correct_answer,
                        "explanation": question.explanation,
                        "concepts": question.concepts,
                        "difficulty": question.difficulty,
                    },
                    student_answer=student_answer,
                    professor_context=professor_context,
                )
            )
        except (ValidationError, TypeError, ValueError, KeyError) as exc:
            logger.warning(
                "invalid_grading_output",
                extra={
                    "exam_id": str(exam_id),
                    "question_id": str(question.id),
                    "error": str(exc),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI grading returned an invalid response. Please try again.",
            ) from exc
        except Exception as exc:
            logger.exception(
                "grading_provider_error",
                extra={"exam_id": str(exam_id), "question_id": str(question.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI grading is temporarily unavailable. Please try again.",
            ) from exc

        is_correct = grade.is_correct
        score = grade.score
        feedback = grade.feedback
        grading_tokens += grade.tokens_used

        if is_correct:
            correct_count += 1

        # Persist student response
        sr = StudentResponse(
            exam_id=exam_id,
            question_id=question.id,
            user_id=current_user.id,
            student_answer=student_answer,
            is_correct=is_correct,
            score=score,
            ai_feedback=feedback,
        )
        db.add(sr)

        # Update concept tracking
        await analytics_service.update_concept_tracking(
            db=db,
            user_id=str(current_user.id),
            course_id=str(exam.course_id),
            concepts=question.concepts or [],
            is_correct=is_correct,
        )

        results.append(
            QuestionResult(
                question_id=question.id,
                question_number=question.question_number,
                is_correct=is_correct,
                score=score,
                student_answer=student_answer,
                correct_answer=question.correct_answer,
                ai_feedback=feedback,
                concepts=question.concepts or [],
            )
        )

    total_questions = len(questions_by_id)
    final_score = (correct_count / total_questions * 100) if total_questions > 0 else 0.0

    exam.status = EXAM_STATUS_COMPLETED
    exam.score = final_score
    exam.completed_at = datetime.now(timezone.utc)
    exam.total_tokens_used += grading_tokens

    await db.commit()

    return ExamResult(
        exam_id=exam_id,
        score=final_score,
        total_questions=total_questions,
        correct_count=correct_count,
        results=results,
        total_tokens_used=exam.total_tokens_used,
    )


@router.get("/courses/{course_id}/heatmap", response_model=list[ConceptHeatmapItem])
async def get_concept_heatmap(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConceptHeatmapItem]:
    """Return concept weakness heatmap for the current user in a course."""
    await _assert_course_ownership(course_id, current_user.id, db)

    heatmap_data = await analytics_service.get_heatmap(
        db=db,
        user_id=str(current_user.id),
        course_id=str(course_id),
    )
    return [ConceptHeatmapItem(**item) for item in heatmap_data]
