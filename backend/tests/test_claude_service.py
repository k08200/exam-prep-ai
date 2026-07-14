"""Contract tests for the real Claude service without making network calls."""
import json
from types import SimpleNamespace

import pytest


def _event(name: str, **attributes):
    event_type = type(name, (), {})
    event = event_type()
    for key, value in attributes.items():
        setattr(event, key, value)
    return event


class _FakeStream:
    def __init__(self, events: list[object], final_message: object) -> None:
        self._events = iter(events)
        self._final_message = final_message

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def get_final_message(self):
        return self._final_message


class _FakeMessages:
    def __init__(self, stream: _FakeStream, response: object) -> None:
        self.stream_value = stream
        self.response = response
        self.stream_calls: list[dict] = []
        self.create_calls: list[dict] = []

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return self.stream_value

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self.response


class _FakeClient:
    def __init__(self, messages: _FakeMessages) -> None:
        self.messages = messages


def _final_message() -> SimpleNamespace:
    return SimpleNamespace(
        usage=SimpleNamespace(input_tokens=17, output_tokens=23),
        content=[SimpleNamespace(type="thinking", thinking="reasoning")],
    )


@pytest.mark.asyncio
async def test_real_analysis_uses_current_stream_contract(monkeypatch) -> None:
    """Current Claude analysis uses adaptive thinking and parses streamed JSON."""
    from app.core.config import settings
    from app.services import claude_service as service_module
    from app.services.claude_service import ClaudeService

    analysis = {
        "top_concepts": [],
        "question_types": {
            "multiple_choice": 25,
            "essay": 25,
            "calculation": 25,
            "true_false": 25,
        },
        "topic_distribution": {"Methods": 100},
        "professor_terms": [],
        "exam_patterns": {},
    }
    events = [
        _event(
            "RawMessageStartEvent",
            message=SimpleNamespace(usage=SimpleNamespace(input_tokens=7)),
        ),
        _event(
            "RawContentBlockDeltaEvent",
            delta=SimpleNamespace(type="thinking_delta", thinking="Inspecting materials"),
        ),
        _event(
            "RawContentBlockDeltaEvent",
            delta=SimpleNamespace(type="text_delta", text=json.dumps(analysis)),
        ),
        _event(
            "RawMessageDeltaEvent",
            usage=SimpleNamespace(output_tokens=19),
        ),
    ]
    messages = _FakeMessages(_FakeStream(events, _final_message()), response=None)
    fake_client = _FakeClient(messages)

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "CLAUDE_MODEL", "claude-opus-4-8")
    monkeypatch.setattr(
        service_module.anthropic,
        "AsyncAnthropic",
        lambda api_key: fake_client,
    )

    service = ClaudeService()
    received = [
        event
        async for event in service.analyze_professor_style(
            course_name="Biology", professor_name="Dr. Test", materials_text="cellular energy"
        )
    ]

    complete = received[-1]
    assert complete["type"] == "complete"
    assert complete["analysis"] == analysis
    call = messages.stream_calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": settings.CLAUDE_THINKING_EFFORT}
    assert call["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_real_generation_parses_one_streamed_question(monkeypatch) -> None:
    """The real generation path returns a question event from streamed JSON."""
    from app.core.config import settings
    from app.services import claude_service as service_module
    from app.services.claude_service import ClaudeService

    question = {
        "question_text": "Explain cellular energy transfer.",
        "question_type": "essay",
        "choices": None,
        "correct_answer": "A complete explanation connects photosynthesis and respiration.",
        "explanation": "Both processes transform energy in cells.",
        "concepts": ["Energy"],
        "difficulty": "medium",
    }
    events = [
        _event(
            "RawContentBlockDeltaEvent",
            delta=SimpleNamespace(type="text_delta", text=json.dumps(question)),
        )
    ]
    messages = _FakeMessages(_FakeStream(events, _final_message()), response=None)
    fake_client = _FakeClient(messages)

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "CLAUDE_MODEL", "claude-opus-4-8")
    monkeypatch.setattr(service_module.anthropic, "AsyncAnthropic", lambda api_key: fake_client)

    service = ClaudeService()
    received = [
        event
        async for event in service.generate_exam_questions(
            course_name="Biology",
            analysis={"top_concepts": [], "question_types": {}, "exam_patterns": {}},
            question_count=1,
            mode="standard",
            topics=None,
        )
    ]

    assert received[0]["type"] == "question"
    assert received[0]["question"] == question
    assert received[-1]["type"] == "complete"
    assert messages.stream_calls[0]["thinking"] == {"type": "adaptive"}


@pytest.mark.asyncio
async def test_real_grading_uses_messages_create_and_returns_usage(monkeypatch) -> None:
    """The non-streaming grading path parses feedback and accounts for tokens."""
    from app.core.config import settings
    from app.services import claude_service as service_module
    from app.services.claude_service import ClaudeService

    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                text=json.dumps(
                    {
                        "is_correct": True,
                        "score": 0.9,
                        "feedback": "Strong explanation.",
                    }
                )
            )
        ],
        usage=SimpleNamespace(input_tokens=11, output_tokens=13),
    )
    messages = _FakeMessages(_FakeStream([], _final_message()), response=response)
    fake_client = _FakeClient(messages)

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "CLAUDE_MODEL", "claude-opus-4-8")
    monkeypatch.setattr(service_module.anthropic, "AsyncAnthropic", lambda api_key: fake_client)

    service = ClaudeService()
    grade = await service.grade_response(
        question={
            "question_text": "What is photosynthesis?",
            "question_type": "essay",
            "correct_answer": "Light energy becomes chemical energy.",
            "explanation": "Energy is stored in glucose.",
            "concepts": ["Energy"],
            "difficulty": "easy",
        },
        student_answer="Light energy becomes chemical energy.",
        professor_context="energy conversion",
    )

    assert grade == {
        "is_correct": True,
        "score": 0.9,
        "feedback": "Strong explanation.",
        "tokens_used": 24,
    }
    assert messages.create_calls[0]["model"] == "claude-opus-4-8"
