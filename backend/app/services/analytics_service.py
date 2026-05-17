"""
Analytics service for concept-level tracking and weakness analysis.
"""
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import ConceptTracking


class AnalyticsService:
    """Manages per-user, per-course concept tracking and heatmap data."""

    async def update_concept_tracking(
        self,
        db: AsyncSession,
        user_id: str,
        course_id: str,
        concepts: list[str],
        is_correct: bool,
    ) -> None:
        """
        Upsert ConceptTracking rows for each concept in the list.

        Weakness score formula:
          base_score = 1 - (correct_count / attempts)
          recency_factor = decay based on time since last attempt
          weakness_score = base_score * (1 + recency_penalty if long gap)

        Scores are clamped to [0.0, 1.0].
        """
        now = datetime.now(timezone.utc)
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(course_id)

        for concept in concepts:
            result = await db.execute(
                select(ConceptTracking).where(
                    ConceptTracking.user_id == uid,
                    ConceptTracking.course_id == cid,
                    ConceptTracking.concept == concept,
                )
            )
            tracking = result.scalar_one_or_none()

            if tracking is None:
                tracking = ConceptTracking(
                    user_id=uid,
                    course_id=cid,
                    concept=concept,
                    attempts=0,
                    correct_count=0,
                    incorrect_count=0,
                    weakness_score=1.0,
                )
                db.add(tracking)

            tracking.attempts += 1
            if is_correct:
                tracking.correct_count += 1
            else:
                tracking.incorrect_count += 1

            tracking.last_attempted = now
            tracking.weakness_score = self._compute_weakness_score(
                attempts=tracking.attempts,
                correct_count=tracking.correct_count,
                last_attempted=tracking.last_attempted,
                now=now,
            )

        await db.flush()

    def _compute_weakness_score(
        self,
        attempts: int,
        correct_count: int,
        last_attempted: datetime | None,
        now: datetime,
    ) -> float:
        """
        Compute a recency-weighted weakness score.

        Formula:
          correct_rate = correct_count / attempts
          base_weakness = 1 - correct_rate

          recency_weight: if last_attempted within 7 days → weight 1.0
                          decays exponentially with half-life of 14 days

          weakness_score = base_weakness * (0.5 + 0.5 * recency_weight)
          → recent failures hurt more; old failures decay toward 0.5 base

        Score is clamped to [0.0, 1.0].
        """
        if attempts == 0:
            return 1.0

        correct_rate = correct_count / attempts
        base_weakness = 1.0 - correct_rate

        recency_weight = 1.0
        if last_attempted is not None:
            # Ensure timezone-aware comparison
            if last_attempted.tzinfo is None:
                last_attempted = last_attempted.replace(tzinfo=timezone.utc)
            days_since = (now - last_attempted).total_seconds() / 86400.0
            half_life = 14.0  # days
            recency_weight = math.exp(-days_since * math.log(2) / half_life)

        weakness_score = base_weakness * (0.5 + 0.5 * recency_weight)
        return max(0.0, min(1.0, weakness_score))

    async def get_heatmap(
        self,
        db: AsyncSession,
        user_id: str,
        course_id: str,
    ) -> list[dict]:
        """
        Return all concept tracking records for a user/course,
        sorted by weakness_score descending (weakest concepts first).
        """
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(course_id)

        result = await db.execute(
            select(ConceptTracking)
            .where(
                ConceptTracking.user_id == uid,
                ConceptTracking.course_id == cid,
            )
            .order_by(ConceptTracking.weakness_score.desc())
        )
        records = result.scalars().all()

        return [
            {
                "concept": r.concept,
                "attempts": r.attempts,
                "correct_count": r.correct_count,
                "incorrect_count": r.incorrect_count,
                "weakness_score": r.weakness_score,
                "last_attempted": r.last_attempted,
            }
            for r in records
        ]

    async def get_cram_topics(
        self,
        analysis: dict,
        user_concepts: list[dict],
    ) -> list[str]:
        """
        Combine professor's high-frequency topics with the user's weakest concepts
        to produce a prioritized topic list for cram mode.

        Strategy:
          1. Take top N professor concepts by importance_score
          2. Take top N user weak concepts by weakness_score
          3. Merge with deduplication, professor emphasis weighted first
        """
        # Professor's high-importance concepts
        top_concepts: list[dict] = analysis.get("top_concepts", [])
        prof_topics = [
            c["concept"]
            for c in sorted(top_concepts, key=lambda x: x.get("importance_score", 0), reverse=True)
            if c.get("importance_score", 0) > 0.5
        ][:10]

        # User's weakest concepts
        weak_concepts = [
            c["concept"]
            for c in sorted(user_concepts, key=lambda x: x.get("weakness_score", 0), reverse=True)
            if c.get("weakness_score", 0) > 0.4
        ][:10]

        # Merge: weak concepts that also appear in professor's top list come first,
        # then remaining professor topics, then remaining weak concepts
        seen: set[str] = set()
        merged: list[str] = []

        # Priority 1: intersection (weak AND important)
        for concept in weak_concepts:
            if concept in prof_topics and concept not in seen:
                merged.append(concept)
                seen.add(concept)

        # Priority 2: professor-important topics not yet included
        for concept in prof_topics:
            if concept not in seen:
                merged.append(concept)
                seen.add(concept)

        # Priority 3: weak concepts not yet included
        for concept in weak_concepts:
            if concept not in seen:
                merged.append(concept)
                seen.add(concept)

        return merged
