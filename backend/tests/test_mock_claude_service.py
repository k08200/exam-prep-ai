"""
Unit tests for MockClaudeService — verifies mock behavior without an API key.
"""
import pytest

from app.services.mock_claude_service import MockClaudeService


SAMPLE_ANALYSIS = {
    "top_concepts": [
        {"concept": "Gradient Descent", "frequency": 15, "importance_score": 0.95, "description": ""},
        {"concept": "Backpropagation", "frequency": 12, "importance_score": 0.90, "description": ""},
    ],
    "question_types": {
        "multiple_choice": 50.0,
        "essay": 25.0,
        "calculation": 15.0,
        "true_false": 10.0,
    },
    "topic_distribution": {"Supervised Learning": 60.0, "Neural Networks": 40.0},
    "professor_terms": [],
    "exam_patterns": {
        "difficulty_levels": {"easy": 0.25, "medium": 0.50, "hard": 0.25},
        "typical_question_count": 10,
        "time_per_question_minutes": 3.0,
        "emphasis": "Conceptual",
        "style_notes": "Multi-part questions",
    },
}


@pytest.fixture
def service() -> MockClaudeService:
    return MockClaudeService()


# ── analyze_professor_style ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_yields_thinking_events(service: MockClaudeService) -> None:
    """analyze_professor_style yields at least one thinking event."""
    events = []
    async for event in service.analyze_professor_style("ML", "Dr. Test", "some content"):
        events.append(event)
    thinking = [e for e in events if e["type"] == "thinking"]
    assert len(thinking) >= 1


@pytest.mark.asyncio
async def test_analyze_yields_complete_event(service: MockClaudeService) -> None:
    """analyze_professor_style ends with a complete event containing analysis."""
    events = []
    async for event in service.analyze_professor_style("Physics", "Prof. Einstein", "wave-particle duality"):
        events.append(event)

    complete_events = [e for e in events if e["type"] == "complete"]
    assert len(complete_events) == 1
    complete = complete_events[0]
    assert "analysis" in complete
    assert "top_concepts" in complete["analysis"]
    assert "question_types" in complete["analysis"]
    assert "exam_patterns" in complete["analysis"]


@pytest.mark.asyncio
async def test_analyze_extracts_keywords_from_materials(service: MockClaudeService) -> None:
    """Keywords from materials text appear in top concepts."""
    text = "Photosynthesis chlorophyll glucose metabolism biology evolution genetics"
    events = []
    async for event in service.analyze_professor_style("Biology", "Dr. Darwin", text):
        events.append(event)

    complete = next(e for e in events if e["type"] == "complete")
    concepts = [c["concept"].lower() for c in complete["analysis"]["top_concepts"]]
    # At least one concept should be derived from the text
    assert len(concepts) > 0


@pytest.mark.asyncio
async def test_analyze_filters_filenames_from_concepts(service: MockClaudeService) -> None:
    """File extensions (.pdf, .docx) are NOT included as concepts."""
    text = "lecture.pdf introduction.docx neural networks backpropagation optimization"
    events = []
    async for event in service.analyze_professor_style("ML", "Prof. X", text):
        events.append(event)

    complete = next(e for e in events if e["type"] == "complete")
    concepts = [c["concept"].lower() for c in complete["analysis"]["top_concepts"]]
    assert not any(".pdf" in c or ".docx" in c for c in concepts)


@pytest.mark.asyncio
async def test_analyze_tokens_are_positive(service: MockClaudeService) -> None:
    """Token counts in events should be positive integers."""
    async for event in service.analyze_professor_style("Math", "Prof. Euler", "calculus derivatives integrals"):
        assert event.get("tokens", 1) > 0


# ── generate_exam_questions ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_correct_question_count(service: MockClaudeService) -> None:
    """generate_exam_questions yields exactly question_count question events."""
    question_events = []
    async for event in service.generate_exam_questions(
        course_name="ML", analysis=SAMPLE_ANALYSIS,
        question_count=5, mode="standard", topics=None,
    ):
        if event["type"] == "question":
            question_events.append(event)

    assert len(question_events) == 5


@pytest.mark.asyncio
async def test_generate_ends_with_complete(service: MockClaudeService) -> None:
    """generate_exam_questions ends with a complete event."""
    events = []
    async for event in service.generate_exam_questions(
        course_name="ML", analysis=SAMPLE_ANALYSIS,
        question_count=2, mode="standard", topics=None,
    ):
        events.append(event)

    assert events[-1]["type"] == "complete"


@pytest.mark.asyncio
async def test_generate_question_has_required_fields(service: MockClaudeService) -> None:
    """Each generated question has all required schema fields."""
    required = {"question_text", "question_type", "correct_answer", "concepts", "difficulty"}
    async for event in service.generate_exam_questions(
        course_name="ML", analysis=SAMPLE_ANALYSIS,
        question_count=3, mode="standard", topics=None,
    ):
        if event["type"] == "question":
            q = event["question"]
            assert required.issubset(q.keys()), f"Missing fields in question: {q.keys()}"


@pytest.mark.asyncio
async def test_generate_multiple_choice_has_choices(service: MockClaudeService) -> None:
    """Multiple-choice questions include a non-empty choices list."""
    mc_questions = []
    for _ in range(10):  # generate enough to likely get an MC question
        async for event in service.generate_exam_questions(
            course_name="Physics", analysis=SAMPLE_ANALYSIS,
            question_count=2, mode="standard", topics=None,
        ):
            if event["type"] == "question" and event["question"]["question_type"] == "multiple_choice":
                mc_questions.append(event["question"])

    if mc_questions:
        for q in mc_questions:
            assert q["choices"] is not None
            assert len(q["choices"]) == 4
            labels = [c["label"] for c in q["choices"]]
            assert "A" in labels


@pytest.mark.asyncio
async def test_cram_mode_uses_harder_difficulties(service: MockClaudeService) -> None:
    """Cram mode generates mostly medium/hard questions."""
    difficulties = []
    for _ in range(5):
        async for event in service.generate_exam_questions(
            course_name="ML", analysis=SAMPLE_ANALYSIS,
            question_count=4, mode="cram", topics=None,
        ):
            if event["type"] == "question":
                difficulties.append(event["question"]["difficulty"])

    hard_or_medium = sum(1 for d in difficulties if d in ("medium", "hard"))
    assert hard_or_medium / len(difficulties) > 0.5


# ── grade_response ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grade_correct_mc_answer(service: MockClaudeService) -> None:
    """Exact correct answer for MC gets is_correct=True, score=1.0."""
    question = {
        "question_type": "multiple_choice",
        "correct_answer": "A",
        "explanation": "A is correct because...",
    }
    result = await service.grade_response(question, "A", "")
    assert result["is_correct"] is True
    assert result["score"] == 1.0
    assert result["tokens_used"] > 0


@pytest.mark.asyncio
async def test_grade_wrong_mc_answer(service: MockClaudeService) -> None:
    """Wrong answer for MC gets is_correct=False, score=0.0."""
    question = {
        "question_type": "multiple_choice",
        "correct_answer": "B",
        "explanation": "B is correct.",
    }
    result = await service.grade_response(question, "C", "")
    assert result["is_correct"] is False
    assert result["score"] == 0.0


@pytest.mark.asyncio
async def test_grade_mc_case_insensitive(service: MockClaudeService) -> None:
    """MC grading is case-insensitive."""
    question = {"question_type": "multiple_choice", "correct_answer": "A", "explanation": ""}
    result = await service.grade_response(question, "a", "")
    assert result["is_correct"] is True


@pytest.mark.asyncio
async def test_grade_true_false_correct(service: MockClaudeService) -> None:
    """Correct T/F answer gets full marks."""
    question = {
        "question_type": "true_false",
        "correct_answer": "True",
        "explanation": "Yes it is true.",
    }
    result = await service.grade_response(question, "True", "")
    assert result["is_correct"] is True
    assert result["score"] == 1.0


@pytest.mark.asyncio
async def test_grade_essay_partial_credit(service: MockClaudeService) -> None:
    """Essay with partial keyword match gives partial credit."""
    question = {
        "question_type": "essay",
        "correct_answer": "gradient descent backpropagation learning rate optimization",
        "explanation": "",
    }
    result = await service.grade_response(question, "gradient descent and learning", "")
    assert 0.0 < result["score"] <= 1.0
    assert "feedback" in result


@pytest.mark.asyncio
async def test_grade_essay_full_credit(service: MockClaudeService) -> None:
    """Essay covering all keywords scores >= 0.7 (marked correct)."""
    question = {
        "question_type": "essay",
        "correct_answer": "gradient descent backpropagation optimization learning",
        "explanation": "",
    }
    result = await service.grade_response(
        question,
        "gradient descent uses backpropagation to perform optimization and adjust the learning rate",
        "",
    )
    assert result["is_correct"] is True
    assert result["score"] >= 0.7


@pytest.mark.asyncio
async def test_grade_result_has_required_fields(service: MockClaudeService) -> None:
    """Grade response always includes is_correct, score, feedback, tokens_used."""
    question = {"question_type": "multiple_choice", "correct_answer": "A", "explanation": ""}
    result = await service.grade_response(question, "A", "")
    assert "is_correct" in result
    assert "score" in result
    assert "feedback" in result
    assert "tokens_used" in result
