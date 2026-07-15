"""Smoke test the configured real AI provider and model configuration.

Usage:
    USE_MOCK_CLAUDE=false AI_PROVIDER=anthropic ANTHROPIC_API_KEY=... python scripts/claude_smoke.py
    USE_MOCK_CLAUDE=false AI_PROVIDER=openrouter OPENROUTER_API_KEY=... python scripts/claude_smoke.py

Set CLAUDE_SMOKE_STREAM=true to also verify streaming analysis events with a
small thinking budget.
"""
from __future__ import annotations

import asyncio
import json
import os

from app.core.config import settings
from app.schemas.exam import GradeResponse
from app.services import get_claude_service


async def main() -> None:
    if settings.active_ai_provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic.")
    if settings.active_ai_provider == "openrouter" and not settings.OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter.")
    if settings.active_ai_provider not in {"anthropic", "openrouter"}:
        raise SystemExit("AI_PROVIDER must be either 'anthropic' or 'openrouter'.")

    settings.USE_MOCK_CLAUDE = False
    service = get_claude_service()

    grade = await service.grade_response(
        question={
            "question_text": "What is photosynthesis?",
            "question_type": "essay",
            "correct_answer": "Plants convert light energy into chemical energy.",
            "explanation": "Photosynthesis stores light energy as chemical energy.",
            "concepts": ["Photosynthesis"],
            "difficulty": "easy",
        },
        student_answer="Plants use light to make stored chemical energy.",
        professor_context="energy conversion, chloroplasts",
    )

    validated_grade = GradeResponse.model_validate(grade)

    stream_checked = False
    if os.getenv("CLAUDE_SMOKE_STREAM", "").lower() in {"1", "true", "yes"}:
        settings.THINKING_BUDGET_ANALYSIS = int(
            os.getenv("CLAUDE_SMOKE_THINKING_BUDGET", "1024")
        )
        completed = False
        validated_analysis = None
        async for event in service.analyze_professor_style(
            course_name="Smoke Test Biology",
            professor_name="Dr. Smoke",
            materials_text=(
                "Photosynthesis converts light energy into chemical energy. "
                "Cellular respiration releases energy from glucose."
            ),
        ):
            if event.get("type") == "complete":
                completed = True
                from app.routers.analysis import _validate_analysis_payload

                validated_analysis = _validate_analysis_payload(event.get("analysis"))
                break
        if not completed:
            raise RuntimeError("AI provider streaming smoke test did not complete.")
        if validated_analysis is None:
            raise RuntimeError("AI provider streaming smoke test returned no analysis payload.")
        stream_checked = True

    print(
        json.dumps(
            {
                "status": "ok",
                "provider": settings.active_ai_provider,
                "model": (
                    settings.OPENROUTER_MODEL
                    if settings.active_ai_provider == "openrouter"
                    else settings.CLAUDE_MODEL
                ),
                "grade_score": validated_grade.score,
                "grade_tokens_used": validated_grade.tokens_used,
                "stream_checked": stream_checked,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
