"""Add daily per-user AI usage counters.

Revision ID: 0004_daily_ai_usage
Revises: 0003_user_token_version
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_daily_ai_usage"
down_revision = "0003_user_token_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_ai_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("analyses_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("questions_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("responses_graded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_daily_ai_usage_user_date"),
    )
    op.create_index("ix_daily_ai_usage_user_id", "daily_ai_usage", ["user_id"])
    op.create_index("ix_daily_ai_usage_date", "daily_ai_usage", ["usage_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_ai_usage_date", table_name="daily_ai_usage")
    op.drop_index("ix_daily_ai_usage_user_id", table_name="daily_ai_usage")
    op.drop_table("daily_ai_usage")
