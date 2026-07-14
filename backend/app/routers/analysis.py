import logging
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user
from app.core.sse import iter_with_heartbeat, sse_event
from app.models.analysis import ProfessorAnalysis
from app.models.analysis_run import AnalysisRun
from app.models.course import Course
from app.models.material import (
    Material,
    PROCESSING_STATUS_COMPLETED,
    PROCESSING_STATUS_PENDING,
    PROCESSING_STATUS_PROCESSING,
)
from app.models.user import User
from app.schemas.analysis import AnalysisResponse, ConceptItem, ProfessorTerm, QuestionTypeDistribution
from app.services import get_claude_service
from app.services.material_quality import is_usable_extracted_text
from app.services.ai_usage_service import AIUsageService

router = APIRouter(tags=["analysis"])
claude_service = get_claude_service()
logger = logging.getLogger(__name__)
ai_usage_service = AIUsageService()
MATERIAL_SEPARATOR = "\n\n---\n\n"
TRUNCATION_MARKER = "\n[Additional material text omitted due to the analysis input limit.]\n"
MaterialSnapshot = tuple[tuple[uuid.UUID, str, str], ...]


def _build_materials_text(materials: list[Material]) -> tuple[str, bool]:
    """Build a bounded, labelled prompt from completed material text."""
    limit = max(settings.MAX_ANALYSIS_INPUT_CHARS, 1)
    sections: list[str] = []
    used_chars = 0
    truncated = False

    for material in materials:
        separator = MATERIAL_SEPARATOR if sections else ""
        header = f"[File: {material.original_filename}]\n"
        text = material.extracted_text or ""
        available = limit - used_chars - len(separator) - len(header)
        if available <= 0:
            truncated = True
            break

        if len(text) > available:
            marker = TRUNCATION_MARKER[:available]
            content_budget = max(available - len(marker), 0)
            text = text[:content_budget] + marker
            truncated = True

        section = f"{header}{text}"
        sections.append(section)
        used_chars += len(separator) + len(section)

        if truncated:
            break

    if len(sections) < len(materials):
        truncated = True

    return MATERIAL_SEPARATOR.join(sections), truncated


def _material_snapshot(materials: list[Material]) -> MaterialSnapshot:
    """Capture the material state that an in-flight analysis is based on."""
    entries = [
        (
            material.id,
            material.processing_status,
            sha256((material.extracted_text or "").encode("utf-8")).hexdigest(),
        )
        for material in materials
    ]
    return tuple(sorted(entries))


async def _materials_still_match(
    course_id: uuid.UUID,
    expected_snapshot: MaterialSnapshot,
    db: AsyncSession,
) -> bool:
    """Ensure analysis output is never saved for a changed material set."""
    result = await db.execute(
        select(Material)
        .where(Material.course_id == course_id)
        .order_by(Material.id.asc())
    )
    return _material_snapshot(list(result.scalars().all())) == expected_snapshot


def _validate_analysis_payload(payload: dict) -> dict:
    """Validate and normalize Claude's structured analysis before persistence."""
    if not isinstance(payload, dict):
        raise TypeError("analysis payload must be an object")

    question_types = QuestionTypeDistribution.model_validate(payload.get("question_types", {}))
    top_concepts = [ConceptItem.model_validate(item) for item in payload.get("top_concepts", [])]
    professor_terms = [ProfessorTerm.model_validate(item) for item in payload.get("professor_terms", [])]
    raw_topic_distribution = payload.get("topic_distribution")
    if raw_topic_distribution is None:
        raw_topic_distribution = {}
    if not isinstance(raw_topic_distribution, dict):
        raise TypeError("topic_distribution must be an object")
    topic_distribution = {
        str(topic): float(weight)
        for topic, weight in raw_topic_distribution.items()
    }
    exam_patterns = payload.get("exam_patterns") or {}
    if not isinstance(exam_patterns, dict):
        raise ValueError("exam_patterns must be an object")

    return {
        "top_concepts": [item.model_dump() for item in top_concepts],
        "question_types": question_types.model_dump(),
        "topic_distribution": topic_distribution,
        "professor_terms": [item.model_dump() for item in professor_terms],
        "exam_patterns": exam_patterns,
    }


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


async def _acquire_analysis_run(course_id: uuid.UUID, db: AsyncSession) -> bool:
    """Atomically reserve the course analysis slot across backend instances."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.ANALYSIS_RUN_STALE_MINUTES)
    try:
        async with db.begin_nested():
            await db.execute(
                delete(AnalysisRun).where(
                    AnalysisRun.course_id == course_id,
                    AnalysisRun.created_at < cutoff,
                )
            )
            db.add(AnalysisRun(course_id=course_id))
            await db.flush()
    except IntegrityError:
        return False
    return True


async def _release_analysis_run(course_id: uuid.UUID) -> None:
    """Release the shared run slot after a stream finishes or is cancelled."""
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AnalysisRun).where(AnalysisRun.course_id == course_id))
        await db.commit()


async def _stream_analysis(
    course_id: uuid.UUID,
    course_name: str,
    professor_name: str,
    materials_text: str,
    materials_snapshot: MaterialSnapshot,
    input_was_truncated: bool = False,
) -> AsyncGenerator[str, None]:
    """Internal generator: stream SSE events for professor analysis."""
    raw_text_parts: list[str] = []
    thinking_tokens = 0
    total_tokens = 0
    final_analysis: dict | None = None

    try:
        try:
            yield sse_event({"type": "heartbeat"})
            if input_was_truncated:
                yield sse_event(
                    {
                        "type": "warning",
                        "content": (
                            "Some material text was shortened to fit the analysis limit. "
                            "Run separate analyses with fewer materials for full coverage."
                        ),
                    }
                )
            async for event in iter_with_heartbeat(
                claude_service.analyze_professor_style(
                    course_name=course_name,
                    professor_name=professor_name,
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

        try:
            final_analysis = _validate_analysis_payload(final_analysis)
        except (ValidationError, TypeError, ValueError) as exc:
            logger.warning(
                "invalid_analysis_output",
                extra={"course_id": str(course_id), "error": str(exc)},
            )
            yield sse_event(
                {
                    "type": "error",
                    "content": "AI returned an invalid analysis format. Please try again.",
                    "retryable": True,
                }
            )
            return

        raw_text = "".join(raw_text_parts)

        async with AsyncSessionLocal() as db:
            try:
                if not await _materials_still_match(course_id, materials_snapshot, db):
                    yield sse_event(
                        {
                            "type": "error",
                            "content": (
                                "Course materials changed while analysis was running. "
                                "Run analysis again to include the latest materials."
                            ),
                            "retryable": True,
                        }
                    )
                    return

                existing_result = await db.execute(
                    select(ProfessorAnalysis).where(ProfessorAnalysis.course_id == course_id)
                )
                existing = existing_result.scalar_one_or_none()

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
                        course_id=course_id,
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
                analysis_id = analysis_record.id
            except Exception:
                await db.rollback()
                raise

        yield sse_event(
            {
                "type": "complete",
                "content": "Analysis complete",
                "analysis_id": str(analysis_id),
                "tokens_used": total_tokens,
                "thinking_tokens": thinking_tokens,
            }
        )
    finally:
        await _release_analysis_run(course_id)


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
        select(Material)
        .where(Material.course_id == course_id)
        .order_by(Material.created_at.asc())
    )
    course_materials = list(result.scalars().all())
    completed_materials = [
        material
        for material in course_materials
        if material.processing_status == PROCESSING_STATUS_COMPLETED
    ]
    processing_materials = [
        material
        for material in course_materials
        if material.processing_status
        in {PROCESSING_STATUS_PENDING, PROCESSING_STATUS_PROCESSING}
    ]

    if processing_materials:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Material processing is still in progress. Wait for all files to finish "
                "before running analysis."
            ),
        )

    if not completed_materials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No completed materials found. Please upload and wait for processing.",
        )

    usable_materials = [
        material
        for material in completed_materials
        if is_usable_extracted_text(material.extracted_text)
    ]
    if not usable_materials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No usable text found in completed materials. Upload a text-based "
                "file or a clearer scan before analysis."
            ),
        )

    if not await _acquire_analysis_run(course_id, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already running for this course.",
        )

    try:
        await ai_usage_service.reserve(db, current_user.id, analyses=1)
        await db.commit()
    except Exception:
        await db.rollback()
        await _release_analysis_run(course_id)
        raise

    materials_text, input_was_truncated = _build_materials_text(usable_materials)
    materials_snapshot = _material_snapshot(course_materials)
    course_name = course.name
    professor_name = course.professor_name or "Unknown Professor"

    return StreamingResponse(
        _stream_analysis(
            course_id,
            course_name,
            professor_name,
            materials_text,
            materials_snapshot,
            input_was_truncated=input_was_truncated,
        ),
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
