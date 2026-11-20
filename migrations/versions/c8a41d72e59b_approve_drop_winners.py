"""Require admin approval before publishing drop winners.

Revision ID: c8a41d72e59b
Revises: b7e4c2d91f30
Create Date: 2026-11-20 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8a41d72e59b"
down_revision: Union[str, None] = "b7e4c2d91f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drop_runs", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("drop_runs", sa.Column("approved_by", sa.String(length=128), nullable=True))
    op.execute("UPDATE drop_runs SET approved_at = ran_at")


def downgrade() -> None:
    op.drop_column("drop_runs", "approved_by")
    op.drop_column("drop_runs", "approved_at")
