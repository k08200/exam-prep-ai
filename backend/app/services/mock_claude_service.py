"""
Mock Claude service — works without ANTHROPIC_API_KEY.

Activated when USE_MOCK_CLAUDE=true in environment.
Returns realistic-looking data for local development and demos.
"""
import asyncio
import json
import random
from typing import AsyncGenerator


class MockClaudeService:
    """Drop-in replacement for ClaudeService that requires no API key."""

    async def analyze_professor_style(
        self,
        course_name: str,
        professor_name: str,
        materials_text: str,
    ) -> AsyncGenerator[dict, None]:
        """Stream a mock professor analysis."""
        thinking_chunks = [
            f"Analyzing course materials for {course_name}...",
            f"Identifying {professor_name}'s examination patterns...",
            "Scanning for recurring concepts and terminology...",
            "Determining question type distribution...",
            "Building topic distribution map...",
            "Finalizing professor style profile...",
        ]

        # Stream thinking events
        for chunk in thinking_chunks:
            await asyncio.sleep(0.3)
            yield {"type": "thinking", "content": chunk, "tokens": 500}

        # Stream text events (simulate JSON being written)
        analysis = _build_mock_analysis(course_name, professor_name, materials_text)
        analysis_json = json.dumps(analysis, indent=2, ensure_ascii=False)

        chunk_size = 80
        tokens_so_far = 1000
        for i in range(0, len(analysis_json), chunk_size):
            await asyncio.sleep(0.05)
            tokens_so_far += 30
            yield {
                "type": "text",
                "content": analysis_json[i : i + chunk_size],
                "tokens": tokens_so_far,
            }

        yield {
            "type": "complete",
            "analysis": analysis,
            "tokens": tokens_so_far + 200,
            "thinking_tokens": 3000,
        }

    async def generate_exam_questions(
        self,
        course_name: str,
        analysis: dict,
        question_count: int,
        mode: str,
        topics: list[str] | None,
    ) -> AsyncGenerator[dict, None]:
        """Stream mock exam question generation."""
        top_concepts = [c["concept"] for c in analysis.get("top_concepts", [])]
        question_types_dist = analysis.get("question_types", {
            "multiple_choice": 50,
            "essay": 25,
            "calculation": 15,
            "true_false": 10,
        })

        total_tokens = 0
        for i in range(question_count):
            await asyncio.sleep(0.4)
            q_type = _pick_question_type(question_types_dist)
            concept = top_concepts[i % len(top_concepts)] if top_concepts else course_name
            difficulty = _pick_difficulty(mode)

            question = _build_mock_question(
                number=i + 1,
                q_type=q_type,
                concept=concept,
                course_name=course_name,
                difficulty=difficulty,
            )
            total_tokens += 400
            yield {"type": "question", "question": question, "tokens": total_tokens}

        yield {"type": "complete", "tokens": total_tokens}

    async def grade_response(
        self,
        question: dict,
        student_answer: str,
        professor_context: str,
    ) -> dict:
        """Mock grading — exact match for MC/T-F, keyword match for essay/calc."""
        await asyncio.sleep(0.1)
        q_type = question.get("question_type", "essay")
        correct = question.get("correct_answer", "")

        if q_type in ("multiple_choice", "true_false"):
            is_correct = student_answer.strip().upper() == correct.strip().upper()
            score = 1.0 if is_correct else 0.0
            feedback = (
                f"Correct! {question.get('explanation', '')}"
                if is_correct
                else f"Incorrect. The correct answer is {correct}. {question.get('explanation', '')}"
            )
        else:
            # Keyword-based partial scoring for essay/calculation
            keywords = [w.lower() for w in correct.split() if len(w) > 4]
            answer_lower = student_answer.lower()
            matches = sum(1 for kw in keywords if kw in answer_lower)
            score = min(1.0, matches / max(len(keywords), 1)) if keywords else 0.5
            is_correct = score >= 0.7
            feedback = (
                f"Good answer! You covered the key concepts. Score: {score:.0%}"
                if is_correct
                else f"Partial credit. Key points to include: {correct[:200]}. Score: {score:.0%}"
            )

        return {
            "is_correct": is_correct,
            "score": score,
            "feedback": feedback,
            "tokens_used": 120,
        }


# ─── Helpers ────────────────────────────────────────────────────────────────

def _build_mock_analysis(course_name: str, professor_name: str, materials_text: str) -> dict:
    """Generate plausible analysis based on course name and material length."""
    word_count = len(materials_text.split()) if materials_text else 500

    # Extract rough keywords from materials to make it feel real
    words = [w.strip(".,;:()[]{}\"'").lower() for w in materials_text.split() if len(w) > 5]
    word_freq: dict[str, int] = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1
    top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:6]
    keyword_concepts = [w.capitalize() for w, _ in top_words]

    default_concepts = [
        "Core Principles", "Theoretical Frameworks", "Applied Methods",
        "Case Analysis", "Problem Solving", "Critical Evaluation",
        "Data Interpretation", "Conceptual Synthesis", "Practical Application",
        "Advanced Topics",
    ]
    concepts = (keyword_concepts + default_concepts)[:10]

    return {
        "top_concepts": [
            {
                "concept": c,
                "frequency": random.randint(8, 25),
                "importance_score": round(random.uniform(0.6, 1.0), 2),
                "description": f"A key concept in {course_name} frequently emphasized by {professor_name}.",
            }
            for c in concepts
        ],
        "question_types": {
            "multiple_choice": 45.0,
            "essay": 25.0,
            "calculation": 20.0,
            "true_false": 10.0,
        },
        "topic_distribution": {
            concepts[0]: 22.0,
            concepts[1]: 18.0,
            concepts[2]: 16.0,
            concepts[3]: 14.0,
            concepts[4]: 12.0,
            "Other Topics": 18.0,
        },
        "professor_terms": [
            {"term": "empirical evidence", "context": "Used when evaluating claims", "frequency": 12},
            {"term": "theoretical framework", "context": "Introduced in lectures", "frequency": 9},
            {"term": "critical analysis", "context": "Required in essay responses", "frequency": 8},
            {"term": "quantitative methods", "context": "Applied in problem sets", "frequency": 7},
            {"term": "comparative study", "context": "Used in case discussions", "frequency": 6},
        ],
        "exam_patterns": {
            "difficulty_levels": {"easy": 0.25, "medium": 0.50, "hard": 0.25},
            "typical_question_count": 20,
            "time_per_question_minutes": 3.0,
            "emphasis": f"{professor_name} emphasizes application of theory to real-world problems.",
            "style_notes": (
                f"Exams in {course_name} typically combine conceptual understanding "
                f"with analytical problem-solving. {professor_name} favors multi-part questions "
                f"that build on each other."
            ),
        },
    }


def _pick_question_type(dist: dict) -> str:
    types = list(dist.keys())
    weights = [dist.get(t, 25.0) for t in types]
    return random.choices(types, weights=weights, k=1)[0]


def _pick_difficulty(mode: str) -> str:
    if mode == "cram":
        return random.choices(["medium", "hard"], weights=[40, 60])[0]
    return random.choices(["easy", "medium", "hard"], weights=[25, 50, 25])[0]


def _build_mock_question(
    number: int,
    q_type: str,
    concept: str,
    course_name: str,
    difficulty: str,
) -> dict:
    if q_type == "multiple_choice":
        return {
            "question_text": (
                f"Which of the following best describes the role of {concept} in {course_name}?"
            ),
            "question_type": "multiple_choice",
            "choices": [
                {"label": "A", "text": f"It provides the foundational framework for {concept}."},
                {"label": "B", "text": f"It is an ancillary concept with limited application."},
                {"label": "C", "text": f"It contradicts established theories in the field."},
                {"label": "D", "text": f"It applies only in advanced research contexts."},
            ],
            "correct_answer": "A",
            "explanation": (
                f"{concept} is central to {course_name} because it provides the foundational "
                f"framework upon which other concepts are built."
            ),
            "concepts": [concept],
            "difficulty": difficulty,
        }
    elif q_type == "true_false":
        return {
            "question_text": (
                f"{concept} is a fundamental component of the theoretical framework in {course_name}."
            ),
            "question_type": "true_false",
            "choices": [
                {"label": "A", "text": "True"},
                {"label": "B", "text": "False"},
            ],
            "correct_answer": "True",
            "explanation": (
                f"This statement is true. {concept} forms a core part of the theoretical "
                f"underpinnings of {course_name}."
            ),
            "concepts": [concept],
            "difficulty": difficulty,
        }
    elif q_type == "calculation":
        return {
            "question_text": (
                f"Given a system with {concept} operating at 80% efficiency and a baseline "
                f"value of 250 units, calculate the effective output and the percentage deviation "
                f"from the theoretical maximum."
            ),
            "question_type": "calculation",
            "choices": None,
            "correct_answer": (
                "Effective output = 250 × 0.80 = 200 units. "
                "Deviation = (250 - 200) / 250 × 100 = 20%."
            ),
            "explanation": (
                f"Apply the efficiency formula: Output = Base × Efficiency. "
                f"The 20% deviation highlights real-world limitations of {concept}."
            ),
            "concepts": [concept],
            "difficulty": difficulty,
        }
    else:  # essay
        return {
            "question_text": (
                f"Critically evaluate the significance of {concept} in {course_name}. "
                f"Your answer should address its theoretical basis, practical implications, "
                f"and any limitations or criticisms raised in the literature. (15 marks)"
            ),
            "question_type": "essay",
            "choices": None,
            "correct_answer": (
                f"A strong answer discusses: (1) theoretical basis of {concept}, "
                f"(2) practical applications with examples, "
                f"(3) known limitations or critiques, "
                f"(4) current research directions."
            ),
            "explanation": (
                f"Full marks require engaging critically with {concept} rather than merely "
                f"describing it. Use specific examples from the course materials."
            ),
            "concepts": [concept],
            "difficulty": difficulty,
        }
