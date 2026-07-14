"""Add shared in-flight analysis locks.

Revision ID: 0005_analysis_runs
Revises: 0004_daily_ai_usage
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_analysis_runs"
down_revision = "0004_daily_ai_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("course_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_runs")
