"""Reconcile legacy local databases with the current ORM contract.

Revision ID: 0006_reconcile_legacy_schema
Revises: 0005_analysis_runs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_reconcile_legacy_schema"
down_revision = "0005_analysis_runs"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    if index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _make_not_null(table_name: str, column_name: str, fallback_sql: str) -> None:
    columns = _columns(table_name)
    if column_name not in columns or not columns[column_name]["nullable"]:
        return
    op.execute(
        sa.text(
            f"UPDATE {table_name} SET {column_name} = {fallback_sql} "
            f"WHERE {column_name} IS NULL"
        )
    )
    op.alter_column(table_name, column_name, nullable=False)


def _alter_varchar(table_name: str, column_name: str, length: int) -> None:
    if column_name in _columns(table_name):
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
                f"TYPE VARCHAR({length})"
            )
        )


def _convert_json_to_jsonb(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
                f"TYPE JSONB USING {column_name}::jsonb"
            )
        )


def upgrade() -> None:
    """Bring old docker volumes forward without discarding study data."""
    if op.get_bind().dialect.name != "postgresql":
        return

    # Users and courses created by the pre-Alembic prototype used nullable
    # timestamps and differently named indexes/constraints.
    _make_not_null("users", "is_active", "TRUE")
    _make_not_null("users", "created_at", "NOW()")
    _make_not_null("users", "updated_at", "NOW()")
    if "users_email_key" in _unique_constraints("users"):
        op.drop_constraint("users_email_key", "users", type_="unique")
    _drop_index_if_present("users", "idx_users_email")
    _create_index_if_missing("users", "ix_users_email", ["email"], unique=True)

    _make_not_null("courses", "created_at", "NOW()")
    _make_not_null("courses", "updated_at", "NOW()")
    _drop_index_if_present("courses", "idx_courses_user_id")
    _create_index_if_missing("courses", "ix_courses_user_id", ["user_id"])

    # Uploaded file metadata was widened after the original prototype so
    # realistic lecture filenames and volume paths are never truncated.
    _alter_varchar("materials", "filename", 512)
    _alter_varchar("materials", "original_filename", 512)
    _alter_varchar("materials", "file_type", 20)
    _alter_varchar("materials", "file_path", 1024)
    _alter_varchar("materials", "processing_status", 20)
    _make_not_null("materials", "processing_status", "'pending'")
    _make_not_null("materials", "created_at", "NOW()")
    _drop_index_if_present("materials", "idx_materials_course_id")
    _drop_index_if_present("materials", "idx_materials_status")
    _create_index_if_missing("materials", "ix_materials_course_id", ["course_id"])
    _create_index_if_missing(
        "materials", "ix_materials_processing_status", ["processing_status"]
    )

    for column_name, fallback in (
        ("top_concepts", "'[]'::jsonb"),
        ("question_types", "'{}'::jsonb"),
        ("topic_distribution", "'{}'::jsonb"),
        ("professor_terms", "'[]'::jsonb"),
        ("exam_patterns", "'{}'::jsonb"),
    ):
        _convert_json_to_jsonb("professor_analyses", column_name)
        _make_not_null("professor_analyses", column_name, fallback)
    _make_not_null("professor_analyses", "thinking_tokens_used", "0")
    _make_not_null("professor_analyses", "total_tokens_used", "0")
    _make_not_null("professor_analyses", "created_at", "NOW()")
    _make_not_null("professor_analyses", "updated_at", "NOW()")
    if "professor_analyses_course_id_key" in _unique_constraints("professor_analyses"):
        op.drop_constraint(
            "professor_analyses_course_id_key",
            "professor_analyses",
            type_="unique",
        )
    _drop_index_if_present("professor_analyses", "idx_analyses_course_id")
    _create_index_if_missing(
        "professor_analyses", "ix_professor_analyses_course_id", ["course_id"], unique=True
    )

    _alter_varchar("exams", "title", 512)
    _alter_varchar("exams", "mode", 20)
    _alter_varchar("exams", "status", 20)
    _make_not_null("exams", "mode", "'standard'")
    _make_not_null("exams", "status", "'draft'")
    _make_not_null("exams", "total_tokens_used", "0")
    _make_not_null("exams", "created_at", "NOW()")
    _make_not_null("exams", "updated_at", "NOW()")
    _drop_index_if_present("exams", "idx_exams_course_id")
    _drop_index_if_present("exams", "idx_exams_user_id")
    _create_index_if_missing("exams", "ix_exams_course_id", ["course_id"])
    _create_index_if_missing("exams", "ix_exams_status", ["status"])
    _create_index_if_missing("exams", "ix_exams_user_id", ["user_id"])

    _alter_varchar("exam_questions", "question_type", 30)
    _alter_varchar("exam_questions", "difficulty", 10)
    _convert_json_to_jsonb("exam_questions", "choices")
    _convert_json_to_jsonb("exam_questions", "concepts")
    _make_not_null("exam_questions", "explanation", "''")
    _make_not_null("exam_questions", "concepts", "'[]'::jsonb")
    _make_not_null("exam_questions", "difficulty", "'medium'")
    _make_not_null("exam_questions", "tokens_used", "0")
    if "created_at" not in _columns("exam_questions"):
        op.add_column(
            "exam_questions",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )
    _make_not_null("exam_questions", "created_at", "NOW()")
    _drop_index_if_present("exam_questions", "idx_questions_exam_id")
    _create_index_if_missing("exam_questions", "ix_exam_questions_exam_id", ["exam_id"])

    _make_not_null("student_responses", "created_at", "NOW()")
    _drop_index_if_present("student_responses", "idx_responses_exam_id")
    _drop_index_if_present("student_responses", "idx_responses_user_id")
    _create_index_if_missing("student_responses", "ix_student_responses_exam_id", ["exam_id"])
    _create_index_if_missing(
        "student_responses", "ix_student_responses_question_id", ["question_id"]
    )
    _create_index_if_missing("student_responses", "ix_student_responses_user_id", ["user_id"])

    _alter_varchar("concept_tracking", "concept", 512)
    _make_not_null("concept_tracking", "attempts", "0")
    _make_not_null("concept_tracking", "correct_count", "0")
    _make_not_null("concept_tracking", "incorrect_count", "0")
    _make_not_null("concept_tracking", "weakness_score", "1.0")
    _make_not_null("concept_tracking", "updated_at", "NOW()")
    if "concept_tracking_user_id_course_id_concept_key" in _unique_constraints(
        "concept_tracking"
    ):
        op.drop_constraint(
            "concept_tracking_user_id_course_id_concept_key",
            "concept_tracking",
            type_="unique",
        )
    if "uq_concept_tracking_user_course_concept" not in _unique_constraints(
        "concept_tracking"
    ):
        op.create_unique_constraint(
            "uq_concept_tracking_user_course_concept",
            "concept_tracking",
            ["user_id", "course_id", "concept"],
        )
    _drop_index_if_present("concept_tracking", "idx_tracking_user_course")
    _create_index_if_missing("concept_tracking", "ix_concept_tracking_concept", ["concept"])
    _create_index_if_missing("concept_tracking", "ix_concept_tracking_course_id", ["course_id"])
    _create_index_if_missing("concept_tracking", "ix_concept_tracking_user_id", ["user_id"])


def downgrade() -> None:
    """The reconciliation only preserves and strengthens existing data."""
    # Reversing this migration would reintroduce unsafe legacy schema behavior.
    pass
