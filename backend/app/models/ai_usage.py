import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DailyAIUsage(Base):
    """Per-user AI work reserved for one UTC calendar day."""

    __tablename__ = "daily_ai_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_daily_ai_usage_user_date"),
        Index("ix_daily_ai_usage_date", "usage_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    analyses_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    responses_graded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="daily_ai_usage")  # noqa: F821
