"""
Unit tests for AnalyticsService and FileParser service layer.
"""
import os
import tempfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import AnalyticsService
from app.services.file_parser import FileParser


@pytest.fixture
def analytics() -> AnalyticsService:
    return AnalyticsService()


@pytest.fixture
def parser() -> FileParser:
    return FileParser()


# ── AnalyticsService ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_concept_tracking_new(
    analytics: AnalyticsService, db_session: AsyncSession
) -> None:
    """First wrong answer on a concept creates a tracking record with high weakness."""
    import uuid
    user_id = str(uuid.uuid4())
    course_id = str(uuid.uuid4())

    await analytics.update_concept_tracking(
        db=db_session,
        user_id=user_id,
        course_id=course_id,
        concepts=["Gradient Descent"],
        is_correct=False,
    )
    await db_session.flush()

    from sqlalchemy import select
    from app.models.exam import ConceptTracking
    result = await db_session.execute(
        select(ConceptTracking).where(
            ConceptTracking.user_id == uuid.UUID(user_id),
            ConceptTracking.concept == "Gradient Descent",
        )
    )
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.weakness_score > 0.5


@pytest.mark.asyncio
async def test_update_concept_tracking_correct_reduces_weakness(
    analytics: AnalyticsService, db_session: AsyncSession
) -> None:
    """Correct answer on a tracked concept reduces its weakness score."""
    import uuid
    user_id = str(uuid.uuid4())
    course_id = str(uuid.uuid4())

    # First: wrong answer (high weakness)
    await analytics.update_concept_tracking(
        db=db_session, user_id=user_id, course_id=course_id,
        concepts=["Backprop"], is_correct=False,
    )
    await db_session.flush()

    from sqlalchemy import select
    from app.models.exam import ConceptTracking
    result = await db_session.execute(
        select(ConceptTracking).where(
            ConceptTracking.user_id == uuid.UUID(user_id),
            ConceptTracking.concept == "Backprop",
        )
    )
    after_wrong = result.scalar_one().weakness_score

    # Then: correct answer (should reduce weakness)
    await analytics.update_concept_tracking(
        db=db_session, user_id=user_id, course_id=course_id,
        concepts=["Backprop"], is_correct=True,
    )
    await db_session.flush()

    result2 = await db_session.execute(
        select(ConceptTracking).where(
            ConceptTracking.user_id == uuid.UUID(user_id),
            ConceptTracking.concept == "Backprop",
        )
    )
    after_correct = result2.scalar_one().weakness_score
    assert after_correct < after_wrong


@pytest.mark.asyncio
async def test_get_heatmap_returns_sorted(
    analytics: AnalyticsService, db_session: AsyncSession
) -> None:
    """get_heatmap returns concepts sorted by weakness descending."""
    import uuid
    user_id = str(uuid.uuid4())
    course_id = str(uuid.uuid4())

    # Create two concepts with different weakness scores
    await analytics.update_concept_tracking(
        db=db_session, user_id=user_id, course_id=course_id,
        concepts=["Easy Topic"], is_correct=True,
    )
    await analytics.update_concept_tracking(
        db=db_session, user_id=user_id, course_id=course_id,
        concepts=["Hard Topic"], is_correct=False,
    )
    await db_session.flush()

    heatmap = await analytics.get_heatmap(db=db_session, user_id=user_id, course_id=course_id)
    assert len(heatmap) >= 1
    scores = [item["weakness_score"] for item in heatmap]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_get_heatmap_empty(
    analytics: AnalyticsService, db_session: AsyncSession
) -> None:
    """get_heatmap returns empty list when no tracking data exists."""
    import uuid
    heatmap = await analytics.get_heatmap(
        db=db_session,
        user_id=str(uuid.uuid4()),
        course_id=str(uuid.uuid4()),
    )
    assert heatmap == []


@pytest.mark.asyncio
async def test_get_cram_topics_uses_weak_concepts(analytics: AnalyticsService) -> None:
    """get_cram_topics returns topics biased toward weak user concepts."""
    analysis = {
        "top_concepts": [
            {"concept": "Gradient Descent", "importance_score": 0.9},
            {"concept": "Backpropagation", "importance_score": 0.8},
            {"concept": "Attention", "importance_score": 0.7},
        ],
        "topic_distribution": {
            "Gradient Descent": 40.0,
            "Backpropagation": 35.0,
            "Attention": 25.0,
        },
    }
    user_concepts = [
        {"concept": "Backpropagation", "weakness_score": 0.9},
        {"concept": "Gradient Descent", "weakness_score": 0.2},
    ]
    topics = await analytics.get_cram_topics(analysis=analysis, user_concepts=user_concepts)
    assert isinstance(topics, list)
    assert len(topics) > 0
    # Weakest concept (Backpropagation) should appear in cram topics
    assert "Backpropagation" in topics


@pytest.mark.asyncio
async def test_get_cram_topics_no_user_data(analytics: AnalyticsService) -> None:
    """get_cram_topics with no user data returns high-importance concepts."""
    analysis = {
        "top_concepts": [
            {"concept": "Neural Networks", "importance_score": 0.95},
        ],
        "topic_distribution": {"Neural Networks": 100.0},
    }
    topics = await analytics.get_cram_topics(analysis=analysis, user_concepts=[])
    assert isinstance(topics, list)
    assert len(topics) > 0


@pytest.mark.asyncio
async def test_get_cram_topics_intersection_priority(analytics: AnalyticsService) -> None:
    """Concepts that are both weak AND professor-important come first in cram topics."""
    analysis = {
        "top_concepts": [
            {"concept": "Gradient Descent", "importance_score": 0.95},
            {"concept": "Overfitting", "importance_score": 0.85},
        ],
        "topic_distribution": {},
    }
    user_concepts = [
        {"concept": "Gradient Descent", "weakness_score": 0.9},
        {"concept": "Regularization", "weakness_score": 0.8},
    ]
    topics = await analytics.get_cram_topics(analysis=analysis, user_concepts=user_concepts)
    # Gradient Descent is in both weak AND prof-important → should be first
    assert "Gradient Descent" in topics
    assert topics.index("Gradient Descent") == 0


def test_compute_weakness_score_zero_attempts(analytics: AnalyticsService) -> None:
    """_compute_weakness_score returns 1.0 when attempts == 0."""
    from datetime import datetime, timezone
    score = analytics._compute_weakness_score(
        attempts=0, correct_count=0,
        last_attempted=None, now=datetime.now(timezone.utc),
    )
    assert score == 1.0


def test_compute_weakness_score_timezone_naive(analytics: AnalyticsService) -> None:
    """_compute_weakness_score handles timezone-naive last_attempted."""
    from datetime import datetime, timezone
    naive_dt = datetime(2025, 1, 1, 12, 0, 0)  # no tzinfo
    now = datetime.now(timezone.utc)
    score = analytics._compute_weakness_score(
        attempts=2, correct_count=1, last_attempted=naive_dt, now=now
    )
    assert 0.0 <= score <= 1.0


def test_compute_weakness_score_all_correct(analytics: AnalyticsService) -> None:
    """Perfect score yields weakness near 0."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    score = analytics._compute_weakness_score(
        attempts=10, correct_count=10, last_attempted=now, now=now
    )
    assert score < 0.1


def test_compute_weakness_score_all_wrong(analytics: AnalyticsService) -> None:
    """All wrong yields weakness near 1."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    score = analytics._compute_weakness_score(
        attempts=10, correct_count=0, last_attempted=now, now=now
    )
    assert score > 0.7


def test_compute_weakness_score_no_last_attempted(analytics: AnalyticsService) -> None:
    """None last_attempted uses default recency weight of 1.0."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    score = analytics._compute_weakness_score(
        attempts=4, correct_count=2, last_attempted=None, now=now
    )
    assert 0.0 <= score <= 1.0


# ── FileParser ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_parser_pdf_text_fallback(parser: FileParser) -> None:
    """PDF parser falls back to text reading when file is plain text with .pdf ext."""
    content = "Machine learning neural networks optimization backpropagation"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode="w") as f:
        f.write(content)
        path = f.name

    try:
        result = await parser.parse_pdf(path)
        assert result["text"].strip() == content.strip()
        assert result["page_count"] == 1
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_file_parser_docx_with_table(parser: FileParser) -> None:
    """DOCX parser extracts table cell content."""
    import io
    from docx import Document

    doc = Document()
    doc.add_paragraph("Introduction paragraph")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Header A"
    table.cell(0, 1).text = "Header B"
    table.cell(1, 0).text = "Value 1"
    table.cell(1, 1).text = "Value 2"

    buf = io.BytesIO()
    doc.save(buf)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(buf.getvalue())
        path = f.name

    try:
        result = await parser.parse_docx(path)
        assert "Introduction paragraph" in result["text"]
        assert "Header A" in result["text"]
        assert "Value 1" in result["text"]
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_file_parser_dispatch_pdf(parser: FileParser) -> None:
    """parse_file dispatches correctly to parse_pdf for 'pdf' type."""
    import fitz
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Dispatch test content")
        doc.save(path)
        doc.close()

        result = await parser.parse_file(path, "pdf")
        assert "Dispatch test content" in result["text"]
        assert result["page_count"] == 1
    finally:
        os.unlink(path)


def test_get_claude_service_returns_mock_when_flag_set(monkeypatch) -> None:
    """get_claude_service() returns MockClaudeService when USE_MOCK_CLAUDE=True."""
    from app.core.config import settings
    from app.services import get_claude_service
    from app.services.mock_claude_service import MockClaudeService

    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", True)
    service = get_claude_service()
    assert isinstance(service, MockClaudeService)


def test_get_claude_service_requires_key_for_real_mode(monkeypatch) -> None:
    """Real Claude mode fails fast when the API key is missing."""
    from app.core.config import settings
    from app.services import get_claude_service

    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_claude_service()


def test_default_claude_model_is_valid_api_id() -> None:
    """Default model uses the Anthropic API model identifier, not a display name."""
    from app.core.config import settings

    assert settings.CLAUDE_MODEL == "claude-opus-4-1-20250805"


def test_cors_origins_are_parsed_from_comma_separated_string(monkeypatch) -> None:
    """Settings exposes CORS origins as a trimmed list for FastAPI middleware."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com, http://localhost:3000 ")

    assert settings.cors_origins == [
        "https://app.example.com",
        "http://localhost:3000",
    ]


def test_validate_runtime_settings_allows_development_defaults(monkeypatch) -> None:
    """Development mode permits mock/local defaults."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    settings.validate_runtime_settings()


def test_validate_runtime_settings_rejects_production_mock_mode(monkeypatch) -> None:
    """Production mode fails fast if mock Claude is enabled."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 40)
    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com")

    with pytest.raises(RuntimeError, match="USE_MOCK_CLAUDE"):
        settings.validate_runtime_settings()


def test_validate_runtime_settings_accepts_safe_production(monkeypatch) -> None:
    """Production mode accepts explicit secret, Claude key, migrations, and CORS."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 40)
    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com")

    settings.validate_runtime_settings()


def test_validate_runtime_settings_rejects_bad_timeout(monkeypatch) -> None:
    """Production mode rejects non-positive request timeout settings."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 40)
    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setattr(settings, "REQUEST_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_MAX_FAILURES", 5)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)

    with pytest.raises(RuntimeError, match="REQUEST_TIMEOUT_SECONDS"):
        settings.validate_runtime_settings()


@pytest.mark.asyncio
async def test_health_endpoint(client) -> None:
    """GET /health returns liveness and AI mode metadata."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ai_mode"] == "mock"
    assert data["claude_configured"] is False


@pytest.mark.asyncio
async def test_request_id_header_is_returned(client) -> None:
    """The request middleware returns caller-provided request IDs for tracing."""
    resp = await client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "test-request-id"


@pytest.mark.asyncio
async def test_request_context_middleware_times_out(monkeypatch) -> None:
    """The request middleware returns 504 when request setup exceeds timeout."""
    import asyncio
    from starlette.requests import Request
    from starlette.responses import Response

    from app.core.config import settings
    from app.core.middleware import request_context_middleware

    monkeypatch.setattr(settings, "REQUEST_TIMEOUT_SECONDS", 0.001)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def slow_call_next(request: Request) -> Response:
        await asyncio.sleep(0.01)
        return Response("ok")

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/slow",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
        },
        receive,
    )

    response = await request_context_middleware(request, slow_call_next)

    assert response.status_code == 504
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_file_parser_dispatch_pptx(parser: FileParser) -> None:
    """parse_file dispatches correctly to parse_pptx for 'pptx' type."""
    import io
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    tf = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    tf.text_frame.text = "Dispatch PPTX test"
    buf = io.BytesIO()
    prs.save(buf)

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        f.write(buf.getvalue())
        path = f.name

    try:
        result = await parser.parse_file(path, "pptx")
        assert "Dispatch PPTX test" in result["text"]
    finally:
        os.unlink(path)
