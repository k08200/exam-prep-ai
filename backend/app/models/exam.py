import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy.types import JSON  # type: ignore
from sqlalchemy import text

from app.core.database import Base

EXAM_STATUS_DRAFT = "draft"
EXAM_STATUS_ACTIVE = "active"
EXAM_STATUS_COMPLETED = "completed"

EXAM_MODE_STANDARD = "standard"
EXAM_MODE_CRAM = "cram"

QUESTION_TYPE_MULTIPLE_CHOICE = "multiple_choice"
QUESTION_TYPE_ESSAY = "essay"
QUESTION_TYPE_CALCULATION = "calculation"
QUESTION_TYPE_TRUE_FALSE = "true_false"

DIFFICULTY_EASY = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD = "hard"


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        Index(
            "uq_exams_one_draft_per_course",
            "course_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(20), default=EXAM_MODE_STANDARD, nullable=False
    )
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=EXAM_STATUS_DRAFT, nullable=False, index=True
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    course: Mapped["Course"] = relationship("Course", back_populates="exams")  # noqa: F821
    user: Mapped["User"] = relationship("User", back_populates="exams")  # noqa: F821
    questions: Mapped[list["ExamQuestion"]] = relationship(
        "ExamQuestion", back_populates="exam", cascade="all, delete-orphan",
        order_by="ExamQuestion.question_number",
    )
    student_responses: Mapped[list["StudentResponse"]] = relationship(
        "StudentResponse", back_populates="exam", cascade="all, delete-orphan"
    )


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # For multiple_choice: [{"label": "A", "text": "..."}, ...]
    choices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    # list of concept names this question tests
    concepts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="questions")
    student_responses: Mapped[list["StudentResponse"]] = relationship(
        "StudentResponse", back_populates="question", cascade="all, delete-orphan"
    )


class StudentResponse(Base):
    __tablename__ = "student_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exam_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="student_responses")
    question: Mapped["ExamQuestion"] = relationship(
        "ExamQuestion", back_populates="student_responses"
    )
    user: Mapped["User"] = relationship("User", back_populates="student_responses")  # noqa: F821


class ConceptTracking(Base):
    __tablename__ = "concept_tracking"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # weakness_score = 1 - correct_rate, weighted by recency (0.0 to 1.0)
    weakness_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="concept_tracking")  # noqa: F821
    course: Mapped["Course"] = relationship("Course", back_populates="concept_tracking")  # noqa: F821
