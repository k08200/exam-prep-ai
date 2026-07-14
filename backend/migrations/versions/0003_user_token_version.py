"""invalidate sessions after password changes

Revision ID: 0003_user_token_version
Revises: 0002_exam_generation_guard
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_user_token_version"
down_revision: Union[str, None] = "0002_exam_generation_guard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a version counter used to invalidate older JWTs."""
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("users", "token_version", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "token_version")
