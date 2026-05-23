"""
TDD tests for the professor analysis endpoints.
The ClaudeService is fully mocked — no real API calls.
"""
import json
import uuid
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import ProfessorAnalysis
from app.models.material import Material, PROCESSING_STATUS_COMPLETED


# ---------------------------------------------------------------------------
# Fixtures: analysis result fixture
# ---------------------------------------------------------------------------

MOCK_ANALYSIS = {
    "top_concepts": [
        {
            "concept": "Gradient Descent",
            "frequency": 15,
            "importance_score": 0.95,
            "description": "Optimisation algorithm",
        },
        {
            "concept": "Backpropagation",
            "frequency": 12,
            "importance_score": 0.90,
            "description": "Neural network training",
        },
    ],
    "question_types": {
        "multiple_choice": 40.0,
        "essay": 30.0,
        "calculation": 20.0,
        "true_false": 10.0,
    },
    "topic_distribution": {
        "Supervised Learning": 40.0,
        "Neural Networks": 35.0,
        "Unsupervised Learning": 25.0,
    },
    "professor_terms": [
        {"term": "loss surface", "context": "optimisation discussion", "frequency": 8},
    ],
    "exam_patterns": {
        "difficulty_levels": {"easy": 20.0, "medium": 50.0, "hard": 30.0},
        "typical_question_count": 20,
        "time_per_question_minutes": 3.0,
        "emphasis": "Conceptual understanding and mathematical derivation",
        "style_notes": "Professor always includes one multi-step calculation problem",
    },
}


async def _create_completed_material(
    db: AsyncSession, course_id: uuid.UUID
) -> Material:
    """Helper: insert a completed material record."""
    mat = Material(
        course_id=course_id,
        filename="test_lecture.pdf",
        original_filename="test_lecture.pdf",
        file_type="pdf",
        file_path="/tmp/test_lecture.pdf",
        file_size=1024,
        extracted_text="This is the lecture content about Gradient Descent and Backpropagation.",
        page_count=5,
        processing_status=PROCESSING_STATUS_COMPLETED,
    )
    db.add(mat)
    await db.flush()
    return mat


async def _mock_analyze_generator():
    """Yield fake SSE-like events matching the real ClaudeService output format."""
    yield {"type": "thinking", "content": "Analysing professor patterns...", "tokens": 100}
    yield {"type": "text", "content": json.dumps(MOCK_ANALYSIS), "tokens": 500}
    yield {
        "type": "complete",
        "analysis": MOCK_ANALYSIS,
        "tokens": 600,
        "thinking_tokens": 100,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_creates_analysis_record(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """Calling POST /courses/{id}/analysis creates a ProfessorAnalysis record in DB."""
    course_id = test_course["id"]

    # Insert a completed material so the endpoint doesn't reject the request
    await _create_completed_material(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.analysis.claude_service.analyze_professor_style",
        return_value=_mock_analyze_generator(),
    ):
        resp = await client.post(
            f"/courses/{course_id}/analysis",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    # SSE response body — check for "complete" event
    body = resp.text
    assert '"type": "complete"' in body or '"type":"complete"' in body

    # Verify DB record was created
    result = await db_session.execute(
        select(ProfessorAnalysis).where(
            ProfessorAnalysis.course_id == uuid.UUID(course_id)
        )
    )
    analysis = result.scalar_one_or_none()
    assert analysis is not None
    assert len(analysis.top_concepts) == 2
    assert analysis.question_types["multiple_choice"] == 40.0


@pytest.mark.asyncio
async def test_analysis_conflict_when_course_already_running(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """A second analysis request for the same course is rejected while one is running."""
    from app.routers.analysis import _analysis_course_locks

    course_id = uuid.UUID(test_course["id"])
    await _create_completed_material(db_session, course_id)
    await db_session.commit()
    _analysis_course_locks.add(course_id)

    try:
        resp = await client.post(f"/courses/{course_id}/analysis", headers=auth_headers)
    finally:
        _analysis_course_locks.discard(course_id)

    assert resp.status_code == 409
    assert "already running" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_analysis_lock_released_after_completion(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """The in-flight analysis lock is released after the stream completes."""
    from app.routers.analysis import _analysis_course_locks

    course_id = uuid.UUID(test_course["id"])
    await _create_completed_material(db_session, course_id)
    await db_session.commit()

    with patch(
        "app.routers.analysis.claude_service.analyze_professor_style",
        return_value=_mock_analyze_generator(),
    ):
        resp = await client.post(f"/courses/{course_id}/analysis", headers=auth_headers)

    assert resp.status_code == 200
    assert course_id not in _analysis_course_locks


@pytest.mark.asyncio
async def test_analysis_lock_released_after_stream_error(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """The in-flight analysis lock is released when the provider stream errors."""
    from app.routers.analysis import _analysis_course_locks

    async def error_generator():
        yield {"type": "error", "content": "provider busy", "retryable": True}

    course_id = uuid.UUID(test_course["id"])
    await _create_completed_material(db_session, course_id)
    await db_session.commit()

    with patch(
        "app.routers.analysis.claude_service.analyze_professor_style",
        return_value=error_generator(),
    ):
        resp = await client.post(f"/courses/{course_id}/analysis", headers=auth_headers)

    assert resp.status_code == 200
    assert "provider busy" in resp.text
    assert course_id not in _analysis_course_locks


@pytest.mark.asyncio
async def test_get_analysis_returns_saved(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """GET /courses/{id}/analysis returns the saved analysis after it has been run."""
    course_id = test_course["id"]

    # Pre-create the analysis record directly
    analysis = ProfessorAnalysis(
        course_id=uuid.UUID(course_id),
        top_concepts=MOCK_ANALYSIS["top_concepts"],
        question_types=MOCK_ANALYSIS["question_types"],
        topic_distribution=MOCK_ANALYSIS["topic_distribution"],
        professor_terms=MOCK_ANALYSIS["professor_terms"],
        exam_patterns=MOCK_ANALYSIS["exam_patterns"],
        raw_analysis="raw text",
        thinking_tokens_used=100,
        total_tokens_used=600,
    )
    db_session.add(analysis)
    await db_session.commit()

    resp = await client.get(f"/courses/{course_id}/analysis", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["course_id"] == course_id
    assert len(data["top_concepts"]) == 2
    assert data["top_concepts"][0]["concept"] == "Gradient Descent"
    assert data["question_types"]["multiple_choice"] == 40.0
    assert data["thinking_tokens_used"] == 100


@pytest.mark.asyncio
async def test_analysis_without_materials_fails(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
) -> None:
    """POST /courses/{id}/analysis returns 422 when no completed materials exist."""
    course_id = test_course["id"]
    # Do NOT add any materials to the course

    resp = await client.post(
        f"/courses/{course_id}/analysis",
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "No completed materials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_analysis_not_found_returns_404(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    """GET analysis for a course with no analysis returns 404."""
    # Create a fresh course with no analysis
    course_resp = await client.post(
        "/courses",
        json={"name": "Empty Course"},
        headers=auth_headers,
    )
    course_id = course_resp.json()["id"]

    resp = await client.get(f"/courses/{course_id}/analysis", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_analysis_streaming_format(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """The SSE stream contains properly formatted data events."""
    course_id = test_course["id"]
    await _create_completed_material(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.analysis.claude_service.analyze_professor_style",
        return_value=_mock_analyze_generator(),
    ):
        resp = await client.post(
            f"/courses/{course_id}/analysis",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # Each non-empty line should start with "data: "
    lines = [ln for ln in resp.text.splitlines() if ln.strip()]
    for line in lines:
        assert line.startswith("data: "), f"Unexpected SSE line: {line!r}"
        # Payload must be valid JSON
        json.loads(line[len("data: "):])


@pytest.mark.asyncio
async def test_analysis_stream_timeout_returns_retryable_error(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """A stalled analysis stream emits heartbeat frames then a retryable timeout error."""
    from app.core.config import settings

    course_id = test_course["id"]
    await _create_completed_material(db_session, uuid.UUID(course_id))
    await db_session.commit()
    monkeypatch.setattr(settings, "AI_STREAM_HEARTBEAT_SECONDS", 0.001)
    monkeypatch.setattr(settings, "AI_STREAM_EVENT_TIMEOUT_SECONDS", 0.004)

    async def stalled_analyze(*args, **kwargs):
        await asyncio.sleep(0.02)
        yield {"type": "text", "content": "late", "tokens": 1}

    with patch(
        "app.routers.analysis.claude_service.analyze_professor_style",
        return_value=stalled_analyze(),
    ):
        resp = await client.post(
            f"/courses/{course_id}/analysis",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    events = [
        json.loads(line[len("data: "):])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert any(event["type"] == "heartbeat" for event in events)
    assert events[-1]["type"] == "error"
    assert events[-1]["retryable"] is True


@pytest.mark.asyncio
async def test_analysis_requires_auth(client: AsyncClient, test_course: dict) -> None:
    """Analysis endpoints require authentication."""
    course_id = test_course["id"]
    resp = await client.post(f"/courses/{course_id}/analysis")
    assert resp.status_code == 401
