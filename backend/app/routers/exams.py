import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
    MultipleChoiceOption,
    QuestionResponse,
    QuestionResult,
)
from app.services.analytics_service import AnalyticsService
from app.services import get_claude_service

router = APIRouter(tags=["exams"])
claude_service = get_claude_service()
analytics_service = AnalyticsService()


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


async def _stream_exam_generation(
    exam: Exam,
    course: Course,
    analysis: ProfessorAnalysis,
    exam_create: ExamCreate,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Stream question generation via SSE, persisting each question as it arrives."""
    total_tokens = 0
    question_number = 1

    # Determine topics for cram mode
    topics = exam_create.topics
    if exam_create.mode == "cram" and not topics:
        user_concepts_result = await db.execute(
            select(ConceptTracking).where(
                ConceptTracking.user_id == exam.user_id,
                ConceptTracking.course_id == exam.course_id,
            ).order_by(ConceptTracking.weakness_score.desc())
        )
        user_concepts = [
            {"concept": ct.concept, "weakness_score": ct.weakness_score}
            for ct in user_concepts_result.scalars().all()
        ]
        topics = await analytics_service.get_cram_topics(
            analysis={
                "top_concepts": analysis.top_concepts,
                "topic_distribution": analysis.topic_distribution,
            },
            user_concepts=user_concepts,
        )

    try:
        yield _sse_event({"type": "heartbeat"})
        async for event in iter_with_heartbeat(
            claude_service.generate_exam_questions(
                course_name=course.name,
                analysis={
                    "top_concepts": analysis.top_concepts,
                    "question_types": analysis.question_types,
                    "topic_distribution": analysis.topic_distribution,
                    "professor_terms": analysis.professor_terms,
                    "exam_patterns": analysis.exam_patterns,
                },
                question_count=exam_create.question_count,
                mode=exam_create.mode,
                topics=topics,
            )
        ):
            event_type = event.get("type")

            if event_type == "heartbeat":
                yield _sse_event(event)
            elif event_type == "error":
                await db.rollback()
                yield _sse_event(event)
                return
            elif event_type == "question":
                q_data = event.get("question", {})
                tokens = event.get("tokens", 0)
                total_tokens += tokens

                question = ExamQuestion(
                    exam_id=exam.id,
                    question_number=question_number,
                    question_text=q_data.get("question_text", ""),
                    question_type=q_data.get("question_type", "essay"),
                    choices=q_data.get("choices"),
                    correct_answer=q_data.get("correct_answer", ""),
                    explanation=q_data.get("explanation", ""),
                    concepts=q_data.get("concepts", []),
                    difficulty=q_data.get("difficulty", "medium"),
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
        await db.rollback()
        yield _sse_event({"type": "error", "content": str(exc), "retryable": True})
        return

    generated_count = question_number - 1
    if generated_count != exam_create.question_count:
        await db.rollback()
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
    exam.status = EXAM_STATUS_ACTIVE
    exam.total_tokens_used = total_tokens
    await db.commit()

    yield _sse_event(
        {
            "type": "complete",
            "exam_id": str(exam.id),
            "total_tokens": total_tokens,
            "question_count": question_number - 1,
        }
    )


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

    exam = Exam(
        course_id=course_id,
        user_id=current_user.id,
        title=exam_create.title,
        mode=exam_create.mode,
        question_count=exam_create.question_count,
        status=EXAM_STATUS_DRAFT,
    )
    db.add(exam)
    await db.flush()
    await db.refresh(exam)

    return StreamingResponse(
        _stream_exam_generation(exam, course, analysis, exam_create, db),
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


@router.post("/exams/{exam_id}/submit", response_model=ExamResult)
async def submit_exam(
    exam_id: uuid.UUID,
    submission: ExamSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamResult:
    """Grade all student answers and return detailed results."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
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

        # Grade the response using Claude
        grade = await claude_service.grade_response(
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

        is_correct = grade["is_correct"]
        score = grade["score"]
        feedback = grade["feedback"]
        grading_tokens += grade.get("tokens_used", 0)

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
