"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-19 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(length=36), "sqlite")


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    if "users" in existing_tables:
        if "materials" in existing_tables:
            _add_column_if_missing(
                "materials",
                sa.Column("processing_error", sa.Text(), nullable=True),
            )
        return

    op.create_table(
        "users",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("user_id", _uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("professor_name", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_courses_user_id"), "courses", ["user_id"], unique=False)

    op.create_table(
        "materials",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("course_id", _uuid_type(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_materials_course_id"), "materials", ["course_id"], unique=False)
    op.create_index(op.f("ix_materials_processing_status"), "materials", ["processing_status"], unique=False)

    op.create_table(
        "professor_analyses",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("course_id", _uuid_type(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("top_concepts", sa.JSON(), nullable=False),
        sa.Column("question_types", sa.JSON(), nullable=False),
        sa.Column("topic_distribution", sa.JSON(), nullable=False),
        sa.Column("professor_terms", sa.JSON(), nullable=False),
        sa.Column("exam_patterns", sa.JSON(), nullable=False),
        sa.Column("raw_analysis", sa.Text(), nullable=True),
        sa.Column("thinking_tokens_used", sa.Integer(), nullable=False),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_professor_analyses_course_id"), "professor_analyses", ["course_id"], unique=True)

    op.create_table(
        "exams",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("course_id", _uuid_type(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", _uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_exams_course_id"), "exams", ["course_id"], unique=False)
    op.create_index(op.f("ix_exams_status"), "exams", ["status"], unique=False)
    op.create_index(op.f("ix_exams_user_id"), "exams", ["user_id"], unique=False)

    op.create_table(
        "concept_tracking",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("user_id", _uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", _uuid_type(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept", sa.String(length=512), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), nullable=False),
        sa.Column("last_attempted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("weakness_score", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_concept_tracking_concept"), "concept_tracking", ["concept"], unique=False)
    op.create_index(op.f("ix_concept_tracking_course_id"), "concept_tracking", ["course_id"], unique=False)
    op.create_index(op.f("ix_concept_tracking_user_id"), "concept_tracking", ["user_id"], unique=False)

    op.create_table(
        "exam_questions",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("exam_id", _uuid_type(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=30), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("concepts", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
    )
    op.create_index(op.f("ix_exam_questions_exam_id"), "exam_questions", ["exam_id"], unique=False)

    op.create_table(
        "student_responses",
        sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
        sa.Column("exam_id", _uuid_type(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", _uuid_type(), sa.ForeignKey("exam_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", _uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_student_responses_exam_id"), "student_responses", ["exam_id"], unique=False)
    op.create_index(op.f("ix_student_responses_question_id"), "student_responses", ["question_id"], unique=False)
    op.create_index(op.f("ix_student_responses_user_id"), "student_responses", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_student_responses_user_id"), table_name="student_responses")
    op.drop_index(op.f("ix_student_responses_question_id"), table_name="student_responses")
    op.drop_index(op.f("ix_student_responses_exam_id"), table_name="student_responses")
    op.drop_table("student_responses")
    op.drop_index(op.f("ix_exam_questions_exam_id"), table_name="exam_questions")
    op.drop_table("exam_questions")
    op.drop_index(op.f("ix_concept_tracking_user_id"), table_name="concept_tracking")
    op.drop_index(op.f("ix_concept_tracking_course_id"), table_name="concept_tracking")
    op.drop_index(op.f("ix_concept_tracking_concept"), table_name="concept_tracking")
    op.drop_table("concept_tracking")
    op.drop_index(op.f("ix_exams_user_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_status"), table_name="exams")
    op.drop_index(op.f("ix_exams_course_id"), table_name="exams")
    op.drop_table("exams")
    op.drop_index(op.f("ix_professor_analyses_course_id"), table_name="professor_analyses")
    op.drop_table("professor_analyses")
    op.drop_index(op.f("ix_materials_processing_status"), table_name="materials")
    op.drop_index(op.f("ix_materials_course_id"), table_name="materials")
    op.drop_table("materials")
    op.drop_index(op.f("ix_courses_user_id"), table_name="courses")
    op.drop_table("courses")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
