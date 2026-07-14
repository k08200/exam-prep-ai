from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_usage import DailyAIUsage
from app.models.user import User


@dataclass(frozen=True)
class AIUsageSnapshot:
    usage_date: date
    analyses_used: int
    questions_generated: int
    responses_graded: int


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _limit_error(label: str, limit: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Daily AI {label} limit reached ({limit}). Try again after the UTC daily reset.",
    )


class AIUsageService:
    """Reserve AI work before a provider request so limits hold across processes."""

    async def get_snapshot(self, db: AsyncSession, user_id) -> AIUsageSnapshot:
        usage_date = _today_utc()
        result = await db.execute(
            select(DailyAIUsage).where(
                DailyAIUsage.user_id == user_id,
                DailyAIUsage.usage_date == usage_date,
            )
        )
        usage = result.scalar_one_or_none()
        return AIUsageSnapshot(
            usage_date=usage_date,
            analyses_used=usage.analyses_used if usage else 0,
            questions_generated=usage.questions_generated if usage else 0,
            responses_graded=usage.responses_graded if usage else 0,
        )

    async def reserve(
        self,
        db: AsyncSession,
        user_id,
        *,
        analyses: int = 0,
        questions: int = 0,
        grades: int = 0,
    ) -> AIUsageSnapshot:
        if min(analyses, questions, grades) < 0:
            raise ValueError("AI usage reservations cannot be negative")

        usage_date = _today_utc()
        # Locking the user row serializes first-use creation and all quota updates.
        user_result = await db.execute(select(User).where(User.id == user_id).with_for_update())
        if user_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        result = await db.execute(
            select(DailyAIUsage)
            .where(DailyAIUsage.user_id == user_id, DailyAIUsage.usage_date == usage_date)
            .with_for_update()
        )
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = DailyAIUsage(user_id=user_id, usage_date=usage_date)
            db.add(usage)
            await db.flush()

        if analyses and usage.analyses_used + analyses > settings.MAX_DAILY_AI_ANALYSES:
            raise _limit_error("analysis", settings.MAX_DAILY_AI_ANALYSES)
        if questions and usage.questions_generated + questions > settings.MAX_DAILY_AI_GENERATED_QUESTIONS:
            raise _limit_error("question generation", settings.MAX_DAILY_AI_GENERATED_QUESTIONS)
        if grades and usage.responses_graded + grades > settings.MAX_DAILY_AI_GRADES:
            raise _limit_error("answer grading", settings.MAX_DAILY_AI_GRADES)

        usage.analyses_used += analyses
        usage.questions_generated += questions
        usage.responses_graded += grades
        await db.flush()
        return AIUsageSnapshot(
            usage_date=usage_date,
            analyses_used=usage.analyses_used,
            questions_generated=usage.questions_generated,
            responses_graded=usage.responses_graded,
        )
