import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    courses: Mapped[list["Course"]] = relationship(  # noqa: F821
        "Course", back_populates="user", cascade="all, delete-orphan"
    )
    exams: Mapped[list["Exam"]] = relationship(  # noqa: F821
        "Exam", back_populates="user", cascade="all, delete-orphan"
    )
    student_responses: Mapped[list["StudentResponse"]] = relationship(  # noqa: F821
        "StudentResponse", back_populates="user", cascade="all, delete-orphan"
    )
    concept_tracking: Mapped[list["ConceptTracking"]] = relationship(  # noqa: F821
        "ConceptTracking", back_populates="user", cascade="all, delete-orphan"
    )
    daily_ai_usage: Mapped[list["DailyAIUsage"]] = relationship(  # noqa: F821
        "DailyAIUsage", back_populates="user", cascade="all, delete-orphan"
    )
