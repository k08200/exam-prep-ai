"""
Claude API integration service.

Extended thinking usage note:
  The Anthropic API supports thinking with:
    thinking={"type": "enabled", "budget_tokens": N}
  There is NO "adaptive" type — we use "enabled" with an explicit budget.
  The betas parameter "interleaved-thinking-2025-05-14" enables interleaved
  thinking blocks between text blocks for more granular streaming.
"""
import json
import logging
import re
from typing import AsyncGenerator

import anthropic

from app.core.config import settings

# Use AsyncAnthropic for non-blocking streaming in async FastAPI context

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are an expert educational analyst specializing in understanding professor exam styles and patterns. Your task is to deeply analyze course materials and extract the professor's examination philosophy, preferred question types, key concepts, and stylistic patterns.

When analyzing materials, focus on:
1. Recurring themes and concepts the professor emphasizes
2. The language and terminology the professor uses
3. The types of problems or questions present in examples
4. Difficulty progression patterns
5. Topics that appear most frequently (likely to be on exams)
6. The professor's pedagogical style (conceptual vs. computational vs. analytical)

You MUST respond with a valid JSON object using this exact structure:
{
  "top_concepts": [
    {"concept": "string", "frequency": integer, "importance_score": float_0_to_1, "description": "string"}
  ],
  "question_types": {
    "multiple_choice": float_percentage,
    "essay": float_percentage,
    "calculation": float_percentage,
    "true_false": float_percentage
  },
  "topic_distribution": {
    "topic_name": float_percentage
  },
  "professor_terms": [
    {"term": "string", "context": "string", "frequency": integer}
  ],
  "exam_patterns": {
    "difficulty_levels": {"easy": float, "medium": float, "hard": float},
    "typical_question_count": integer,
    "time_per_question_minutes": float,
    "emphasis": "string describing the professor's examination emphasis",
    "style_notes": "string describing stylistic patterns"
  }
}

The question_types percentages MUST sum to exactly 100. Be thorough and precise."""

GENERATION_SYSTEM_PROMPT = """You are an expert exam question generator. Using the professor's analyzed style and patterns, generate exam questions that EXACTLY match the professor's examination style.

Each question must:
1. Match the professor's vocabulary and terminology
2. Test concepts at the difficulty level specified
3. Follow the professor's preferred question structure
4. Be educationally sound and unambiguous
5. Include a detailed explanation from the professor's perspective

You MUST respond with a JSON object for each question:
{
  "question_text": "string",
  "question_type": "multiple_choice|essay|calculation|true_false",
  "choices": [{"label": "A", "text": "string"}, ...] or null for non-MC,
  "correct_answer": "string (e.g., 'A' for MC, full answer for essay)",
  "explanation": "string explaining why this is correct, in the professor's style",
  "concepts": ["concept1", "concept2"],
  "difficulty": "easy|medium|hard"
}

Generate one question at a time. Be creative yet accurate."""

GRADING_SYSTEM_PROMPT = """You are an expert exam grader who understands the professor's expectations and grading philosophy. Grade student answers fairly but with the rigor the professor would apply.

For multiple choice: exact match required.
For true/false: exact match required.
For essay and calculation: evaluate completeness, accuracy, and use of correct terminology.

Respond with JSON:
{
  "is_correct": boolean,
  "score": float_0_to_1,
  "feedback": "string — specific, constructive feedback in the professor's style"
}"""


class ClaudeService:
    def __init__(self) -> None:
        # AsyncAnthropic for non-blocking streaming in FastAPI's async context
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL

    async def analyze_professor_style(
        self,
        course_name: str,
        professor_name: str,
        materials_text: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream a deep professor style analysis using extended thinking.

        Yields dicts with keys:
          - {"type": "thinking", "content": str, "tokens": int}
          - {"type": "text", "content": str, "tokens": int}
          - {"type": "complete", "analysis": dict, "tokens": int, "thinking_tokens": int}
        """
        user_prompt = (
            f"Course: {course_name}\n"
            f"Professor: {professor_name}\n\n"
            f"=== COURSE MATERIALS ===\n\n"
            f"{materials_text}\n\n"
            f"=== END OF MATERIALS ===\n\n"
            f"Please analyze these materials thoroughly and provide the structured JSON analysis "
            f"of the professor's examination style and patterns."
        )

        thinking_tokens_used = 0
        output_tokens_used = 0
        input_tokens_used = 0
        raw_text = ""

        # Async streaming with extended thinking.
        # NOTE: thinking.type must be "enabled" — "adaptive" does not exist in the API.
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=settings.THINKING_BUDGET_ANALYSIS + 8192,
            thinking={
                "type": "enabled",
                "budget_tokens": settings.THINKING_BUDGET_ANALYSIS,
            },
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            betas=["interleaved-thinking-2025-05-14"],
        ) as stream:
            async for event in stream:
                event_type = type(event).__name__

                if event_type == "RawContentBlockStartEvent":
                    block = event.content_block
                    if hasattr(block, "type") and block.type == "thinking":
                        pass  # thinking block starting

                elif event_type == "RawContentBlockDeltaEvent":
                    delta = event.delta
                    delta_type = getattr(delta, "type", None)

                    if delta_type == "thinking_delta":
                        thinking_content = getattr(delta, "thinking", "")
                        yield {
                            "type": "thinking",
                            "content": thinking_content,
                            "tokens": thinking_tokens_used,
                        }

                    elif delta_type == "text_delta":
                        text_content = getattr(delta, "text", "")
                        raw_text += text_content
                        yield {
                            "type": "text",
                            "content": text_content,
                            "tokens": output_tokens_used,
                        }

                elif event_type == "RawMessageDeltaEvent":
                    usage = getattr(event, "usage", None)
                    if usage:
                        output_tokens_used = getattr(usage, "output_tokens", output_tokens_used)

                elif event_type == "RawMessageStartEvent":
                    msg = getattr(event, "message", None)
                    if msg and hasattr(msg, "usage"):
                        input_tokens_used = getattr(msg.usage, "input_tokens", 0)

            # Get final usage from the completed message
            final_message = await stream.get_final_message()
            if final_message.usage:
                input_tokens_used = final_message.usage.input_tokens
                output_tokens_used = final_message.usage.output_tokens

            # Count thinking tokens from content blocks
            for block in final_message.content:
                if hasattr(block, "type") and block.type == "thinking":
                    # Estimate thinking tokens from thinking text length
                    thinking_tokens_used += len(getattr(block, "thinking", "")) // 4

        # Parse the JSON from the accumulated text
        analysis = _extract_json(raw_text)
        total_tokens = input_tokens_used + output_tokens_used

        yield {
            "type": "complete",
            "analysis": analysis,
            "tokens": total_tokens,
            "thinking_tokens": thinking_tokens_used,
        }

    async def generate_exam_questions(
        self,
        course_name: str,
        analysis: dict,
        question_count: int,
        mode: str,
        topics: list[str] | None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream exam question generation using extended thinking for style compliance.

        Yields dicts:
          - {"type": "question", "question": dict, "tokens": int}
          - {"type": "complete", "tokens": int}
        """
        top_concepts = analysis.get("top_concepts", [])
        question_types = analysis.get("question_types", {})
        exam_patterns = analysis.get("exam_patterns", {})

        topics_instruction = ""
        if topics:
            topics_instruction = f"\nFocus specifically on these topics: {', '.join(topics)}"
        elif mode == "cram":
            topics_instruction = "\nThis is CRAM mode: focus on the highest-frequency, highest-importance concepts only."

        user_prompt = (
            f"Course: {course_name}\n"
            f"Mode: {mode}\n"
            f"Total questions to generate: {question_count}\n"
            f"{topics_instruction}\n\n"
            f"Professor Analysis Summary:\n"
            f"- Top Concepts: {json.dumps(top_concepts[:10], ensure_ascii=False)}\n"
            f"- Question Type Distribution: {json.dumps(question_types, ensure_ascii=False)}\n"
            f"- Exam Patterns: {json.dumps(exam_patterns, ensure_ascii=False)}\n\n"
            f"Generate exactly {question_count} exam questions that perfectly match this professor's style. "
            f"Output each question as a separate JSON object. "
            f"Adhere strictly to the question type distribution percentages when choosing types. "
            f"Vary difficulty according to the professor's typical patterns."
        )

        total_tokens = 0
        raw_text = ""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=settings.THINKING_BUDGET_GENERATION + question_count * 1000,
            thinking={
                "type": "enabled",
                "budget_tokens": settings.THINKING_BUDGET_GENERATION,
            },
            system=GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            betas=["interleaved-thinking-2025-05-14"],
        ) as stream:
            async for event in stream:
                event_type = type(event).__name__

                if event_type == "RawContentBlockDeltaEvent":
                    delta = event.delta
                    delta_type = getattr(delta, "type", None)
                    if delta_type == "text_delta":
                        raw_text += getattr(delta, "text", "")

                elif event_type == "RawMessageDeltaEvent":
                    usage = getattr(event, "usage", None)
                    if usage:
                        total_tokens = getattr(usage, "output_tokens", total_tokens)

            final_message = await stream.get_final_message()
            if final_message.usage:
                total_tokens = (
                    final_message.usage.input_tokens + final_message.usage.output_tokens
                )

        questions = _extract_all_json_objects(raw_text)
        tokens_per_question = total_tokens // max(len(questions), 1)

        for q in questions[:question_count]:
            yield {"type": "question", "question": q, "tokens": tokens_per_question}

        yield {"type": "complete", "tokens": total_tokens}

    async def grade_response(
        self,
        question: dict,
        student_answer: str,
        professor_context: str,
    ) -> dict:
        """
        Grade a student's answer and return structured feedback.

        Returns: {"is_correct": bool, "score": float, "feedback": str, "tokens_used": int}
        """
        user_prompt = (
            f"Question Type: {question.get('question_type', 'essay')}\n"
            f"Question: {question.get('question_text', '')}\n"
        )

        choices = question.get("choices")
        if choices:
            user_prompt += f"Choices: {json.dumps(choices, ensure_ascii=False)}\n"

        user_prompt += (
            f"Correct Answer: {question.get('correct_answer', '')}\n"
            f"Explanation: {question.get('explanation', '')}\n"
            f"Concepts Tested: {', '.join(question.get('concepts', []))}\n"
            f"Difficulty: {question.get('difficulty', 'medium')}\n"
        )

        if professor_context:
            user_prompt += f"Professor's Key Terms: {professor_context}\n"

        user_prompt += f"\nStudent's Answer: {student_answer}\n\nGrade this answer."

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=GRADING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text += block.text

        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        grade_data = _extract_json(response_text)
        return {
            "is_correct": bool(grade_data.get("is_correct", False)),
            "score": float(grade_data.get("score", 0.0)),
            "feedback": str(grade_data.get("feedback", "No feedback available.")),
            "tokens_used": tokens_used,
        }


def _extract_json(text: str) -> dict:
    """
    Extract the first valid JSON object from a text string.
    Tries direct parse, then code-fence extraction, then regex.
    """
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Code fence (```json ... ```)
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Largest {...} block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not extract JSON from Claude response. Returning empty dict.")
    return {}


def _extract_all_json_objects(text: str) -> list[dict]:
    """
    Extract all top-level JSON objects from a text that may contain
    multiple consecutive or separated JSON objects.
    """
    objects: list[dict] = []
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                fragment = text[start : i + 1]
                try:
                    obj = json.loads(fragment)
                    if isinstance(obj, dict):
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None

    return objects
