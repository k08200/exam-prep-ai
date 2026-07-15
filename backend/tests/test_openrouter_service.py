"""Tests for the OpenRouter provider without real network calls."""
import json

import pytest


class FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeStreamContext:
    def __init__(self, response: FakeStreamResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeStreamResponse:
        return self.response

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeAsyncClient:
    def __init__(self, stream_lines: list[str], grade_payload: dict, calls: list[dict]) -> None:
        self.stream_lines = stream_lines
        self.grade_payload = grade_payload
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    def stream(self, method: str, url: str, **kwargs) -> FakeStreamContext:
        self.calls.append({"method": method, "url": url, **kwargs})
        return FakeStreamContext(FakeStreamResponse(self.stream_lines))

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return FakeResponse(self.grade_payload)


def _configure_openrouter(monkeypatch, stream_lines: list[str], grade_payload: dict) -> list[dict]:
    from app.core.config import settings
    from app.services import openrouter_service

    calls: list[dict] = []
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "anthropic/claude-opus-4.8")
    monkeypatch.setattr(settings, "OPENROUTER_SITE_URL", "https://study.example.com")

    def fake_client_factory(*args, **kwargs):
        return FakeAsyncClient(stream_lines, grade_payload, calls)

    monkeypatch.setattr(openrouter_service.httpx, "AsyncClient", fake_client_factory)
    return calls


def test_openrouter_error_messages_are_actionable() -> None:
    from app.services.openrouter_service import _raise_for_openrouter_error
    import httpx

    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        _raise_for_openrouter_error(httpx.Response(401, request=request))

    with pytest.raises(RuntimeError, match="insufficient account credits"):
        _raise_for_openrouter_error(httpx.Response(402, request=request))

    with pytest.raises(RuntimeError, match="rate-limiting"):
        _raise_for_openrouter_error(httpx.Response(429, request=request))


@pytest.mark.asyncio
async def test_openrouter_analysis_streams_text_reasoning_and_usage(monkeypatch) -> None:
    from app.services.openrouter_service import OpenRouterService

    analysis = {
        "top_concepts": [],
        "question_types": {
            "multiple_choice": 25,
            "essay": 25,
            "calculation": 25,
            "true_false": 25,
        },
        "topic_distribution": {},
        "professor_terms": [],
        "exam_patterns": {},
    }
    content = json.dumps(analysis)
    lines = [
        'data: {"choices":[{"delta":{"reasoning":"Thinking."}}]}',
        f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}",
        'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":34}}',
        "data: [DONE]",
    ]
    calls = _configure_openrouter(monkeypatch, lines, {})

    events = [
        event
        async for event in OpenRouterService().analyze_professor_style(
            course_name="Biology",
            professor_name="Dr. Kim",
            materials_text="Photosynthesis lecture notes",
        )
    ]

    assert events[0]["type"] == "thinking"
    assert events[1] == {"type": "text", "content": content, "tokens": 0}
    assert events[-1]["analysis"] == analysis
    assert events[-1]["tokens"] == 46
    assert calls[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer openrouter-test-key"
    assert calls[0]["headers"]["HTTP-Referer"] == "https://study.example.com"
    assert calls[0]["json"]["stream"] is True


@pytest.mark.asyncio
async def test_openrouter_generation_and_grading(monkeypatch) -> None:
    from app.services.openrouter_service import OpenRouterService

    question = {
        "question_text": "Which organelle makes ATP?",
        "question_type": "multiple_choice",
        "choices": [{"label": "A", "text": "Mitochondrion"}],
        "correct_answer": "A",
        "explanation": "Mitochondria produce ATP.",
        "concepts": ["cellular respiration"],
        "difficulty": "easy",
    }
    stream_lines = [
        f"data: {json.dumps({'choices': [{'delta': {'content': json.dumps(question)}}]})}",
        'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":20}}',
        "data: [DONE]",
    ]
    grade_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"is_correct": True, "score": 1.0, "feedback": "Correct."}
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4},
    }
    calls = _configure_openrouter(monkeypatch, stream_lines, grade_payload)
    service = OpenRouterService()

    events = [
        event
        async for event in service.generate_exam_questions(
            course_name="Biology",
            analysis={},
            question_count=1,
            mode="standard",
            topics=None,
        )
    ]
    grade = await service.grade_response(question, "A", "ATP")

    assert events[0]["question"] == question
    assert events[-1] == {"type": "complete", "tokens": 30}
    assert grade == {
        "is_correct": True,
        "score": 1.0,
        "feedback": "Correct.",
        "tokens_used": 12,
    }
    assert calls[1]["json"]["stream"] is False


def test_get_claude_service_returns_openrouter_when_configured(monkeypatch) -> None:
    from app.core.config import settings
    from app.services import get_claude_service
    from app.services.openrouter_service import OpenRouterService

    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", False)
    monkeypatch.setattr(settings, "AI_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")

    assert isinstance(get_claude_service(), OpenRouterService)


def test_get_claude_service_requires_openrouter_key(monkeypatch) -> None:
    from app.core.config import settings
    from app.services import get_claude_service

    monkeypatch.setattr(settings, "USE_MOCK_CLAUDE", False)
    monkeypatch.setattr(settings, "AI_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_claude_service()
