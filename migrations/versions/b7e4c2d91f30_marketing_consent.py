"""Members' consent to promotional email

Revision ID: b7e4c2d91f30
Revises: f3d1c0a7e2b9
Create Date: 2026-11-18 09:00:00

Adds three columns to consumers. Members who already have an account are
opted in (source "existing_member"); new members start opted out.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7e4c2d91f30'
down_revision: Union[str, None] = 'f3d1c0a7e2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('consumers', sa.Column('marketing_consent', sa.Boolean(), nullable=False,
                                         server_default=sa.false()))
    op.add_column('consumers', sa.Column('marketing_consent_source', sa.String(length=32), nullable=True))
    op.add_column('consumers', sa.Column('marketing_consent_updated_at', sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE consumers SET marketing_consent = 1, marketing_consent_source = 'existing_member', "
        "marketing_consent_updated_at = UTC_TIMESTAMP()"
    )


def downgrade() -> None:
    op.drop_column('consumers', 'marketing_consent_updated_at')
    op.drop_column('consumers', 'marketing_consent_source')
    op.drop_column('consumers', 'marketing_consent')
