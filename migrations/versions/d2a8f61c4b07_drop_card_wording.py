"""Drop card badge and subtext

Revision ID: d2a8f61c4b07
Revises: b7e4c2d91f30
Create Date: 2026-11-18 14:00:00

Adds two optional columns to drops; nothing else changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2a8f61c4b07'
down_revision: Union[str, None] = 'b7e4c2d91f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('drops', sa.Column('card_badge', sa.String(length=64), nullable=True))
    op.add_column('drops', sa.Column('card_subtext', sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column('drops', 'card_subtext')
    op.drop_column('drops', 'card_badge')
