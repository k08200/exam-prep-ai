"""Finish reconciliation for databases upgraded by revision 0006.

Revision ID: 0007_schema_reconcile_fix
Revises: 0006_reconcile_legacy_schema
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0007_schema_reconcile_fix"
down_revision = "0006_reconcile_legacy_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove the final legacy metadata differences without touching study data."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = inspect(bind)
    question_columns = {
        column["name"]: column for column in inspector.get_columns("exam_questions")
    }
    created_at = question_columns.get("created_at")
    if created_at is not None and created_at["nullable"]:
        op.execute(sa.text("UPDATE exam_questions SET created_at = NOW() WHERE created_at IS NULL"))
        op.alter_column("exam_questions", "created_at", nullable=False)

    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "idx_users_email" in user_indexes:
        op.drop_index("idx_users_email", table_name="users")


def downgrade() -> None:
    """Legacy schema metadata is intentionally not restored."""
    pass
