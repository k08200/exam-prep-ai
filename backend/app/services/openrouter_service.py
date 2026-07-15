"""OpenRouter implementation for analysis, exam generation, and grading."""
import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.schemas.exam import GradeResponse
from app.services.claude_service import (
    ANALYSIS_SYSTEM_PROMPT,
    GENERATION_SYSTEM_PROMPT,
    GRADING_SYSTEM_PROMPT,
    _extract_all_json_objects,
    _extract_json,
)

logger = logging.getLogger(__name__)


def _raise_for_openrouter_error(response: httpx.Response) -> None:
    """Raise provider-safe guidance without exposing upstream response details."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        messages = {
            400: "OpenRouter rejected the request. Check the configured model and request limits.",
            401: "OpenRouter rejected the API key. Update OPENROUTER_API_KEY and restart the backend.",
            402: "OpenRouter has insufficient account credits for this request.",
            403: "OpenRouter denied access to the configured model.",
            429: "OpenRouter is rate-limiting requests. Wait a moment and try again.",
        }
        message = messages.get(
            exc.response.status_code,
            "OpenRouter could not complete the AI request. Please try again.",
        )
        raise RuntimeError(message) from exc


def _content_text(content: object) -> str:
    """Normalize OpenRouter content, which can be text or typed content blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text") or block.get("content")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _usage_tokens(usage: object) -> tuple[int, int]:
    """Read token counts from the OpenAI-compatible usage object."""
    if not isinstance(usage, dict):
        return 0, 0
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
    return int(input_tokens or 0), int(output_tokens or 0)


class OpenRouterService:
    """AI service backed by OpenRouter's OpenAI-compatible API."""

    def __init__(self) -> None:
        self.model = settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": settings.OPENROUTER_APP_NAME,
        }
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        return headers

    def _payload(self, system_prompt: str, user_prompt: str, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": stream,
        }

    async def _stream_completion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncGenerator[dict, None]:
        """Yield decoded data chunks from OpenRouter's SSE response."""
        timeout = httpx.Timeout(settings.AI_STREAM_EVENT_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=self._payload(system_prompt, user_prompt, stream=True),
            ) as response:
                _raise_for_openrouter_error(response)
                async for line in response.aiter_lines():
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("openrouter_invalid_sse_chunk")
                        continue
                    if isinstance(chunk, dict):
                        yield chunk

    async def analyze_professor_style(
        self,
        course_name: str,
        professor_name: str,
        materials_text: str,
    ) -> AsyncGenerator[dict, None]:
        user_prompt = (
            f"Course: {course_name}\n"
            f"Professor: {professor_name}\n\n"
            f"=== COURSE MATERIALS ===\n\n"
            f"{materials_text}\n\n"
            f"=== END OF MATERIALS ===\n\n"
            "Please analyze these materials thoroughly and provide the structured JSON analysis "
            "of the professor's examination style and patterns."
        )

        raw_text = ""
        raw_reasoning = ""
        input_tokens = 0
        output_tokens = 0

        async for chunk in self._stream_completion(ANALYSIS_SYSTEM_PROMPT, user_prompt):
            chunk_input, chunk_output = _usage_tokens(chunk.get("usage"))
            input_tokens = max(input_tokens, chunk_input)
            output_tokens = max(output_tokens, chunk_output)

            choices = chunk.get("choices") or []
            if not choices or not isinstance(choices[0], dict):
                continue
            delta = choices[0].get("delta") or {}
            if not isinstance(delta, dict):
                continue

            reasoning = _content_text(delta.get("reasoning"))
            if reasoning:
                raw_reasoning += reasoning
                yield {
                    "type": "thinking",
                    "content": reasoning,
                    "tokens": len(raw_reasoning) // 4,
                }

            content = _content_text(delta.get("content"))
            if content:
                raw_text += content
                yield {"type": "text", "content": content, "tokens": output_tokens}

        yield {
            "type": "complete",
            "analysis": _extract_json(raw_text),
            "tokens": input_tokens + output_tokens,
            "thinking_tokens": len(raw_reasoning) // 4,
        }

    async def generate_exam_questions(
        self,
        course_name: str,
        analysis: dict,
        question_count: int,
        mode: str,
        topics: list[str] | None,
    ) -> AsyncGenerator[dict, None]:
        top_concepts = analysis.get("top_concepts", [])
        question_types = analysis.get("question_types", {})
        exam_patterns = analysis.get("exam_patterns", {})
        topics_instruction = ""
        if topics:
            topics_instruction = f"\nFocus specifically on these topics: {', '.join(topics)}"
        elif mode == "cram":
            topics_instruction = (
                "\nThis is CRAM mode: focus on the highest-frequency, "
                "highest-importance concepts only."
            )

        user_prompt = (
            f"Course: {course_name}\n"
            f"Mode: {mode}\n"
            f"Total questions to generate: {question_count}\n"
            f"{topics_instruction}\n\n"
            "Professor Analysis Summary:\n"
            f"- Top Concepts: {json.dumps(top_concepts[:10], ensure_ascii=False)}\n"
            f"- Question Type Distribution: {json.dumps(question_types, ensure_ascii=False)}\n"
            f"- Exam Patterns: {json.dumps(exam_patterns, ensure_ascii=False)}\n\n"
            f"Generate exactly {question_count} exam questions that perfectly match this professor's style. "
            "Output each question as a separate JSON object. "
            "Adhere strictly to the question type distribution percentages when choosing types. "
            "Vary difficulty according to the professor's typical patterns."
        )

        raw_text = ""
        input_tokens = 0
        output_tokens = 0
        async for chunk in self._stream_completion(GENERATION_SYSTEM_PROMPT, user_prompt):
            chunk_input, chunk_output = _usage_tokens(chunk.get("usage"))
            input_tokens = max(input_tokens, chunk_input)
            output_tokens = max(output_tokens, chunk_output)
            choices = chunk.get("choices") or []
            if choices and isinstance(choices[0], dict):
                delta = choices[0].get("delta") or {}
                if isinstance(delta, dict):
                    raw_text += _content_text(delta.get("content"))

        questions = _extract_all_json_objects(raw_text)
        total_tokens = input_tokens + output_tokens
        tokens_per_question = total_tokens // max(len(questions), 1)
        for question in questions[:question_count]:
            yield {"type": "question", "question": question, "tokens": tokens_per_question}
        yield {"type": "complete", "tokens": total_tokens}

    async def grade_response(
        self,
        question: dict,
        student_answer: str,
        professor_context: str,
    ) -> dict:
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

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=self._payload(GRADING_SYSTEM_PROMPT, user_prompt, stream=False),
            )
            _raise_for_openrouter_error(response)
            payload = response.json()

        choices = payload.get("choices") or []
        message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        response_text = _content_text(message.get("content") if isinstance(message, dict) else "")
        grade = GradeResponse.model_validate(_extract_json(response_text))
        input_tokens, output_tokens = _usage_tokens(payload.get("usage"))
        return {
            "is_correct": grade.is_correct,
            "score": grade.score,
            "feedback": grade.feedback,
            "tokens_used": input_tokens + output_tokens,
        }
