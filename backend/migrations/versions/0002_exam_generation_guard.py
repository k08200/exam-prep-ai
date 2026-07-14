"""prevent concurrent draft exam generations

Revision ID: 0002_exam_generation_guard
Revises: 0001_initial_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_exam_generation_guard"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow at most one in-progress draft generation per course."""
    op.create_index(
        "uq_exams_one_draft_per_course",
        "exams",
        ["course_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )


def downgrade() -> None:
    op.drop_index("uq_exams_one_draft_per_course", table_name="exams")
