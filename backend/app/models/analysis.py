import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy.types import JSON  # type: ignore

from app.core.database import Base


# PostgreSQL is the supported persistent database. Keep JSONB there while
# retaining SQLite compatibility for the fast unit-test suite.
JSON_DOCUMENT = JSONB().with_variant(JSON(), "sqlite")


class ProfessorAnalysis(Base):
    __tablename__ = "professor_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # list of {concept: str, frequency: int, importance_score: float, description: str}
    top_concepts: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    # {multiple_choice: float, essay: float, calculation: float, true_false: float}
    question_types: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    # {topic_name: percentage}
    topic_distribution: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    # list of {term: str, context: str, frequency: int}
    professor_terms: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    # {difficulty_levels: {...}, time_estimates: {...}, ...}
    exam_patterns: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    raw_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
    course: Mapped["Course"] = relationship(  # noqa: F821
        "Course", back_populates="analysis"
    )
