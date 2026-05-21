import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.sse import iter_with_heartbeat, sse_event
from app.models.analysis import ProfessorAnalysis
from app.models.course import Course
from app.models.material import Material, PROCESSING_STATUS_COMPLETED
from app.models.user import User
from app.schemas.analysis import AnalysisResponse, ConceptItem, ProfessorTerm, QuestionTypeDistribution
from app.services import get_claude_service

router = APIRouter(tags=["analysis"])
claude_service = get_claude_service()
_analysis_course_locks: set[uuid.UUID] = set()


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


async def _stream_analysis(
    course: Course,
    materials_text: str,
    db: AsyncSession,
    lock_course_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    """Internal generator: stream SSE events for professor analysis."""
    raw_text_parts: list[str] = []
    thinking_tokens = 0
    total_tokens = 0
    final_analysis: dict | None = None

    try:
        try:
            yield sse_event({"type": "heartbeat"})
            async for event in iter_with_heartbeat(
                claude_service.analyze_professor_style(
                    course_name=course.name,
                    professor_name=course.professor_name or "Unknown Professor",
                    materials_text=materials_text,
                )
            ):
                event_type = event.get("type")
                if event_type == "heartbeat":
                    yield sse_event(event)
                elif event_type == "error":
                    yield sse_event(event)
                    return
                elif event_type == "thinking":
                    thinking_tokens = event.get("tokens", thinking_tokens)
                    yield sse_event(
                        {"type": "thinking", "content": event.get("content", ""), "tokens_used": thinking_tokens}
                    )
                elif event_type == "text":
                    raw_text_parts.append(event.get("content", ""))
                    total_tokens = event.get("tokens", total_tokens)
                    yield sse_event(
                        {"type": "text", "content": event.get("content", ""), "tokens_used": total_tokens}
                    )
                elif event_type == "complete":
                    final_analysis = event.get("analysis")
                    total_tokens = event.get("tokens", total_tokens)
                    thinking_tokens = event.get("thinking_tokens", thinking_tokens)

        except Exception as exc:
            yield sse_event({"type": "error", "content": str(exc), "retryable": True})
            return

        if final_analysis is None:
            yield sse_event(
                {
                    "type": "error",
                    "content": "Analysis did not produce structured output",
                    "retryable": True,
                }
            )
            return

        # Persist / upsert analysis to DB
        existing_result = await db.execute(
            select(ProfessorAnalysis).where(ProfessorAnalysis.course_id == course.id)
        )
        existing = existing_result.scalar_one_or_none()

        raw_text = "".join(raw_text_parts)

        if existing is not None:
            existing.top_concepts = final_analysis.get("top_concepts", [])
            existing.question_types = final_analysis.get("question_types", {})
            existing.topic_distribution = final_analysis.get("topic_distribution", {})
            existing.professor_terms = final_analysis.get("professor_terms", [])
            existing.exam_patterns = final_analysis.get("exam_patterns", {})
            existing.raw_analysis = raw_text
            existing.thinking_tokens_used = thinking_tokens
            existing.total_tokens_used = total_tokens
            analysis_record = existing
        else:
            analysis_record = ProfessorAnalysis(
                course_id=course.id,
                top_concepts=final_analysis.get("top_concepts", []),
                question_types=final_analysis.get("question_types", {}),
                topic_distribution=final_analysis.get("topic_distribution", {}),
                professor_terms=final_analysis.get("professor_terms", []),
                exam_patterns=final_analysis.get("exam_patterns", {}),
                raw_analysis=raw_text,
                thinking_tokens_used=thinking_tokens,
                total_tokens_used=total_tokens,
            )
            db.add(analysis_record)

        await db.commit()
        await db.refresh(analysis_record)

        yield sse_event(
            {
                "type": "complete",
                "content": "Analysis complete",
                "analysis_id": str(analysis_record.id),
                "tokens_used": total_tokens,
                "thinking_tokens": thinking_tokens,
            }
        )
    finally:
        _analysis_course_locks.discard(lock_course_id)


@router.post("/courses/{course_id}/analysis")
async def run_analysis(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Analyse all uploaded materials for a course and stream the results via SSE.
    Requires at least one completed material.
    """
    course = await _assert_course_ownership(course_id, current_user.id, db)

    result = await db.execute(
        select(Material).where(
            Material.course_id == course_id,
            Material.processing_status == PROCESSING_STATUS_COMPLETED,
        )
    )
    completed_materials = result.scalars().all()

    if not completed_materials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No completed materials found. Please upload and wait for processing.",
        )

    if course_id in _analysis_course_locks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already running for this course.",
        )
    _analysis_course_locks.add(course_id)

    materials_text = "\n\n---\n\n".join(
        f"[File: {m.original_filename}]\n{m.extracted_text or ''}"
        for m in completed_materials
    )

    return StreamingResponse(
        _stream_analysis(course, materials_text, db, course_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/courses/{course_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Return the saved professor analysis for a course."""
    await _assert_course_ownership(course_id, current_user.id, db)

    result = await db.execute(
        select(ProfessorAnalysis).where(ProfessorAnalysis.course_id == course_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found. Run POST /courses/{course_id}/analysis first.",
        )

    return AnalysisResponse(
        id=analysis.id,
        course_id=analysis.course_id,
        top_concepts=[ConceptItem(**c) for c in (analysis.top_concepts or [])],
        question_types=QuestionTypeDistribution(**analysis.question_types),
        topic_distribution=analysis.topic_distribution or {},
        professor_terms=[ProfessorTerm(**t) for t in (analysis.professor_terms or [])],
        exam_patterns=analysis.exam_patterns or {},
        thinking_tokens_used=analysis.thinking_tokens_used,
        total_tokens_used=analysis.total_tokens_used,
        created_at=analysis.created_at,
    )
