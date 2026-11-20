"""Merge the drop card and winner approval revisions.

Revision ID: e53a19b72c6d
Revises: c8a41d72e59b, d2a8f61c4b07
Create Date: 2026-11-20 00:00:00
"""
from typing import Sequence, Union

revision: str = "e53a19b72c6d"
down_revision: Union[str, Sequence[str], None] = ("c8a41d72e59b", "d2a8f61c4b07")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
