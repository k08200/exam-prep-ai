import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    professor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    user: Mapped["User"] = relationship("User", back_populates="courses")  # noqa: F821
    materials: Mapped[list["Material"]] = relationship(  # noqa: F821
        "Material", back_populates="course", cascade="all, delete-orphan"
    )
    analysis: Mapped["ProfessorAnalysis | None"] = relationship(  # noqa: F821
        "ProfessorAnalysis",
        back_populates="course",
        uselist=False,
        cascade="all, delete-orphan",
    )
    exams: Mapped[list["Exam"]] = relationship(  # noqa: F821
        "Exam", back_populates="course", cascade="all, delete-orphan"
    )
    concept_tracking: Mapped[list["ConceptTracking"]] = relationship(  # noqa: F821
        "ConceptTracking", back_populates="course", cascade="all, delete-orphan"
    )
