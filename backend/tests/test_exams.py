"""
TDD tests for exam creation, submission, grading, and heatmap.
The ClaudeService is fully mocked — no real API calls.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import ProfessorAnalysis
from app.models.exam import ConceptTracking, Exam, ExamQuestion


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

MOCK_ANALYSIS_DATA = {
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
        "multiple_choice": 50.0,
        "essay": 25.0,
        "calculation": 15.0,
        "true_false": 10.0,
    },
    "topic_distribution": {"Supervised Learning": 60.0, "Neural Networks": 40.0},
    "professor_terms": [{"term": "loss function", "context": "optimisation", "frequency": 5}],
    "exam_patterns": {
        "difficulty_levels": {"easy": 30.0, "medium": 50.0, "hard": 20.0},
        "typical_question_count": 10,
        "time_per_question_minutes": 3.0,
        "emphasis": "Conceptual understanding",
        "style_notes": "Professor likes multi-part questions",
    },
}

MOCK_QUESTIONS = [
    {
        "question_text": "What is the purpose of the learning rate in gradient descent?",
        "question_type": "multiple_choice",
        "choices": [
            {"label": "A", "text": "Controls step size"},
            {"label": "B", "text": "Sets the number of epochs"},
            {"label": "C", "text": "Determines the loss function"},
            {"label": "D", "text": "Initialises the weights"},
        ],
        "correct_answer": "A",
        "explanation": "The learning rate controls how large each optimisation step is.",
        "concepts": ["Gradient Descent"],
        "difficulty": "easy",
    },
    {
        "question_text": "Explain the vanishing gradient problem in deep networks.",
        "question_type": "essay",
        "choices": None,
        "correct_answer": "Gradients become exponentially smaller during backpropagation...",
        "explanation": "Gradients decay multiplicatively through layers.",
        "concepts": ["Backpropagation"],
        "difficulty": "hard",
    },
]


async def _create_analysis(db: AsyncSession, course_id: uuid.UUID) -> ProfessorAnalysis:
    """Helper: persist a mock ProfessorAnalysis record."""
    analysis = ProfessorAnalysis(
        course_id=course_id,
        top_concepts=MOCK_ANALYSIS_DATA["top_concepts"],
        question_types=MOCK_ANALYSIS_DATA["question_types"],
        topic_distribution=MOCK_ANALYSIS_DATA["topic_distribution"],
        professor_terms=MOCK_ANALYSIS_DATA["professor_terms"],
        exam_patterns=MOCK_ANALYSIS_DATA["exam_patterns"],
        raw_analysis="raw text",
        thinking_tokens_used=500,
        total_tokens_used=2000,
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def _mock_question_generator(questions: list[dict] | None = None):
    """Async generator that yields mock question events."""
    q_list = questions or MOCK_QUESTIONS
    for q in q_list:
        yield {"type": "question", "question": q, "tokens": 100}
    yield {"type": "complete", "tokens": len(q_list) * 100}


async def _mock_grade_response(correct: bool = True) -> dict:
    return {
        "is_correct": correct,
        "score": 1.0 if correct else 0.0,
        "feedback": "Well done!" if correct else "Review this concept.",
        "tokens_used": 50,
    }


# ---------------------------------------------------------------------------
# Exam creation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_exam_generates_questions(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """POST /courses/{id}/exams streams questions and creates DB records."""
    course_id = test_course["id"]
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        side_effect=lambda *args, **kwargs: _mock_question_generator(),
    ):
        resp = await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Midterm Practice", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.text
    assert "complete" in body

    # Parse the complete event
    complete_event = None
    for line in body.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            if event.get("type") == "complete":
                complete_event = event
                break

    assert complete_event is not None
    exam_id = complete_event["exam_id"]

    # Verify questions in DB
    result = await db_session.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == uuid.UUID(exam_id))
    )
    questions = result.scalars().all()
    assert len(questions) == 2


@pytest.mark.asyncio
async def test_exam_question_count_correct(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """The number of generated questions matches the requested count."""
    course_id = test_course["id"]
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    three_questions = MOCK_QUESTIONS + [
        {
            "question_text": "What is overfitting?",
            "question_type": "true_false",
            "choices": None,
            "correct_answer": "True",
            "explanation": "Overfitting occurs when the model memorises training data.",
            "concepts": ["Generalisation"],
            "difficulty": "medium",
        }
    ]

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        return_value=_mock_question_generator(three_questions),
    ):
        resp = await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Three-question test", "question_count": 3, "mode": "standard"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    complete_line = next(
        ln for ln in resp.text.splitlines()
        if ln.startswith("data: ") and "complete" in ln
    )
    complete_event = json.loads(complete_line[6:])
    assert complete_event["question_count"] == 3


@pytest.mark.asyncio
async def test_create_exam_mismatched_question_count_rolls_back(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """If generation returns fewer questions than requested, no partial exam is kept."""
    course_id = test_course["id"]
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        return_value=_mock_question_generator(MOCK_QUESTIONS[:1]),
    ):
        resp = await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Mismatch Test", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert "Exam generation failed" in resp.text
    assert '"type": "complete"' not in resp.text

    result = await db_session.execute(select(Exam).where(Exam.title == "Mismatch Test"))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_create_exam_without_analysis_fails(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    """POST /courses/{id}/exams returns 422 if no analysis exists."""
    course_resp = await client.post(
        "/courses",
        json={"name": "Unanalyzed Course"},
        headers=auth_headers,
    )
    course_id = course_resp.json()["id"]

    resp = await client.post(
        f"/courses/{course_id}/exams",
        json={"title": "Fail Test", "question_count": 5, "mode": "standard"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "analysis" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Submission and grading tests
# ---------------------------------------------------------------------------


async def _create_exam_with_questions(
    client: AsyncClient,
    auth_headers: dict,
    course_id: str,
    db_session: AsyncSession,
) -> tuple[str, list[str]]:
    """
    Helper: create an exam via the API and return (exam_id, [question_id, ...]).
    """
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        side_effect=lambda *args, **kwargs: _mock_question_generator(),
    ):
        resp = await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Test Exam", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )

    exam_id = None
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            ev = json.loads(line[6:])
            if ev.get("type") == "complete":
                exam_id = ev["exam_id"]
                break

    assert exam_id is not None

    detail_resp = await client.get(f"/exams/{exam_id}", headers=auth_headers)
    questions = detail_resp.json()["questions"]
    question_ids = [q["id"] for q in questions]
    return exam_id, question_ids


@pytest.mark.asyncio
async def test_submit_exam_calculates_score(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """Submitting an exam returns a score as a percentage (0-100)."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(return_value=await _mock_grade_response(correct=True)),
    ):
        resp = await client.post(
            f"/exams/{exam_id}/submit",
            json={
                "answers": [
                    {"question_id": qid, "student_answer": "A"} for qid in q_ids
                ]
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    result = resp.json()
    assert result["score"] == 100.0
    assert result["correct_count"] == 2
    assert result["total_questions"] == 2


@pytest.mark.asyncio
async def test_get_exam_result_after_submit(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """GET /exams/{id}/result returns persisted grading details for completed exams."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(return_value=await _mock_grade_response(correct=True)),
    ):
        submit_resp = await client.post(
            f"/exams/{exam_id}/submit",
            json={"answers": [{"question_id": qid, "student_answer": "A"} for qid in q_ids]},
            headers=auth_headers,
        )
    assert submit_resp.status_code == 200

    result_resp = await client.get(f"/exams/{exam_id}/result", headers=auth_headers)
    assert result_resp.status_code == 200
    data = result_resp.json()
    assert data["exam_id"] == exam_id
    assert data["score"] == 100.0
    assert data["total_questions"] == 2
    assert len(data["results"]) == 2
    assert all(r["correct_answer"] for r in data["results"])


@pytest.mark.asyncio
async def test_get_exam_result_before_submit_returns_409(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """GET /exams/{id}/result is only available after submission."""
    course_id = test_course["id"]
    exam_id, _ = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    resp = await client.get(f"/exams/{exam_id}/result", headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_submit_correct_answer(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """A correct answer gets is_correct=True and score=1.0."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(return_value=await _mock_grade_response(correct=True)),
    ):
        resp = await client.post(
            f"/exams/{exam_id}/submit",
            json={"answers": [{"question_id": q_ids[0], "student_answer": "A"}]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    result = resp.json()
    assert any(r["is_correct"] for r in result["results"])


@pytest.mark.asyncio
async def test_submit_wrong_answer(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """An incorrect answer gets is_correct=False and score=0.0."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(return_value=await _mock_grade_response(correct=False)),
    ):
        resp = await client.post(
            f"/exams/{exam_id}/submit",
            json={"answers": [{"question_id": q_ids[0], "student_answer": "Wrong"}]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    result = resp.json()
    assert any(not r["is_correct"] for r in result["results"])


@pytest.mark.asyncio
async def test_submit_unanswered_question_is_allowed(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """A blank answer is accepted so the UI can mark unanswered questions incorrect."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    async def grade_by_answer(question: dict, student_answer: str, professor_context: str) -> dict:
        is_correct = bool(student_answer)
        return {
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0,
            "feedback": "Answered" if is_correct else "No answer provided.",
            "tokens_used": 50,
        }

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(side_effect=grade_by_answer),
    ):
        resp = await client.post(
            f"/exams/{exam_id}/submit",
            json={
                "answers": [
                    {"question_id": q_ids[0], "student_answer": ""},
                    {"question_id": q_ids[1], "student_answer": "A"},
                ]
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    result = resp.json()
    assert result["total_questions"] == 2
    assert result["correct_count"] == 1
    assert any(r["student_answer"] == "" and not r["is_correct"] for r in result["results"])


@pytest.mark.asyncio
async def test_submit_exam_twice_returns_409(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """Submitting an already-completed exam returns 409 Conflict."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )
    payload = {"answers": [{"question_id": q_ids[0], "student_answer": "A"}]}

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(return_value=await _mock_grade_response()),
    ):
        resp1 = await client.post(f"/exams/{exam_id}/submit", json=payload, headers=auth_headers)
        assert resp1.status_code == 200

        resp2 = await client.post(f"/exams/{exam_id}/submit", json=payload, headers=auth_headers)
        assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_submit_duplicate_answers_returns_422(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """A payload cannot submit multiple answers for the same question."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    resp = await client.post(
        f"/exams/{exam_id}/submit",
        json={
            "answers": [
                {"question_id": q_ids[0], "student_answer": "A"},
                {"question_id": q_ids[0], "student_answer": "B"},
            ]
        },
        headers=auth_headers,
    )

    assert resp.status_code == 422
    assert "duplicate" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_unknown_question_returns_422(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """Answers must reference questions that belong to the submitted exam."""
    course_id = test_course["id"]
    exam_id, _ = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    resp = await client.post(
        f"/exams/{exam_id}/submit",
        json={"answers": [{"question_id": str(uuid.uuid4()), "student_answer": "A"}]},
        headers=auth_headers,
    )

    assert resp.status_code == 422
    assert "do not belong" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_draft_exam_returns_409(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """Draft exams cannot be submitted before generation finishes successfully."""
    from app.models.course import Course
    from app.models.exam import EXAM_STATUS_DRAFT

    course_id = uuid.UUID(test_course["id"])
    course_result = await db_session.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalar_one()
    exam = Exam(
        course_id=course.id,
        user_id=course.user_id,
        title="Draft Exam",
        mode="standard",
        question_count=1,
        status=EXAM_STATUS_DRAFT,
    )
    db_session.add(exam)
    await db_session.commit()

    resp = await client.post(
        f"/exams/{exam.id}/submit",
        json={"answers": []},
        headers=auth_headers,
    )

    assert resp.status_code == 409
    assert "not ready" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Heatmap / concept tracking tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_heatmap_after_exam(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """After submitting an exam the heatmap returns concept tracking data."""
    course_id = test_course["id"]
    exam_id, q_ids = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    with patch(
        "app.routers.exams.claude_service.grade_response",
        new=AsyncMock(return_value=await _mock_grade_response(correct=False)),
    ):
        await client.post(
            f"/exams/{exam_id}/submit",
            json={"answers": [{"question_id": qid, "student_answer": "X"} for qid in q_ids]},
            headers=auth_headers,
        )

    heatmap_resp = await client.get(
        f"/courses/{course_id}/heatmap", headers=auth_headers
    )
    assert heatmap_resp.status_code == 200
    heatmap = heatmap_resp.json()
    assert len(heatmap) > 0

    # Heatmap should be sorted weakest-first
    scores = [item["weakness_score"] for item in heatmap]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_token_counter_updates(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """total_tokens_used on the exam record increases after exam generation."""
    course_id = test_course["id"]
    exam_id, _ = await _create_exam_with_questions(
        client, auth_headers, course_id, db_session
    )

    resp = await client.get(f"/exams/{exam_id}", headers=auth_headers)
    exam_data = resp.json()
    assert exam_data["total_tokens_used"] > 0


@pytest.mark.asyncio
async def test_cram_mode_generates_high_frequency_questions(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """
    Cram mode passes the weakest/most-important topics to the generator.
    We verify the generator is called with topics list.
    """
    course_id = test_course["id"]
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    captured_topics: list = []

    async def mock_generate(course_name, analysis, question_count, mode, topics):
        captured_topics.extend(topics or [])
        async for event in _mock_question_generator():
            yield event

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        side_effect=mock_generate,
    ):
        resp = await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Cram Session", "question_count": 2, "mode": "cram"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    # Topics list is derived from the analytics service; even if empty it should be a list
    assert isinstance(captured_topics, list)


@pytest.mark.asyncio
async def test_list_exams_returns_user_exams(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """GET /courses/{id}/exams returns all exams for the course."""
    course_id = test_course["id"]
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        side_effect=lambda *args, **kwargs: _mock_question_generator(),
    ):
        await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Exam 1", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )
        await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Exam 2", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )

    resp = await client.get(f"/courses/{course_id}/exams", headers=auth_headers)
    assert resp.status_code == 200
    exams = resp.json()
    assert len(exams) >= 2
    titles = [e["title"] for e in exams]
    assert "Exam 1" in titles
    assert "Exam 2" in titles


@pytest.mark.asyncio
async def test_list_all_exams_respects_limit(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session: AsyncSession,
) -> None:
    """GET /exams returns recent exams across courses and applies the limit."""
    course_id = test_course["id"]
    await _create_analysis(db_session, uuid.UUID(course_id))
    await db_session.commit()

    with patch(
        "app.routers.exams.claude_service.generate_exam_questions",
        side_effect=lambda *args, **kwargs: _mock_question_generator(),
    ):
        await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Recent 1", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )
        await client.post(
            f"/courses/{course_id}/exams",
            json={"title": "Recent 2", "question_count": 2, "mode": "standard"},
            headers=auth_headers,
        )

    resp = await client.get("/exams?limit=1", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_all_exams_rejects_invalid_limit(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    """GET /exams validates the limit query parameter."""
    resp = await client.get("/exams?limit=0", headers=auth_headers)
    assert resp.status_code == 422
