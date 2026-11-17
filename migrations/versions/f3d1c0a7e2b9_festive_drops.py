"""Festive Drops: campaigns, drops, members, picks and crews

Revision ID: f3d1c0a7e2b9
Revises: 8d731acd55df
Create Date: 2026-11-17 16:30:00

Creates tables only; no existing table is changed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3d1c0a7e2b9'
down_revision: Union[str, None] = '8d731acd55df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base():
    return [
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        'campaigns', *_base(),
        sa.Column('slug', sa.String(length=64), nullable=False, unique=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('terms_version', sa.String(length=32), nullable=False),
        sa.Column('max_picks_per_member', sa.Integer(), nullable=False),
    )
    op.create_table(
        'drops', *_base(),
        sa.Column('campaign_id', sa.String(length=64), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('brand', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cover_image', sa.String(length=512), nullable=True),
        sa.Column('kind', sa.Enum('airtime', 'voucher', 'crew', name='drop_kind'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('crew_size', sa.Integer(), nullable=True),
        sa.Column('pick_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('use_within_days', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('upcoming', 'picked', name='drop_status'), nullable=False),
        sa.Column('venue_pin_hash', sa.String(length=256), nullable=True),
    )
    op.create_table(
        'campaign_members', *_base(),
        sa.Column('campaign_id', sa.String(length=64), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('consumer_id', sa.String(length=64), sa.ForeignKey('consumers.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('terms_version', sa.String(length=32), nullable=False),
        sa.UniqueConstraint('campaign_id', 'consumer_id', name='uq_campaign_member'),
    )
    op.create_table(
        'drop_runs', *_base(),
        sa.Column('drop_id', sa.String(length=64), sa.ForeignKey('drops.id'), nullable=False, unique=True),
        sa.Column('ran_at', sa.DateTime(), nullable=False),
        sa.Column('eligible_count', sa.Integer(), nullable=False),
        sa.Column('picked_count', sa.Integer(), nullable=False),
        sa.Column('shortfall', sa.Integer(), nullable=False),
        sa.Column('eligible_digest', sa.String(length=64), nullable=False),
        sa.Column('triggered_by', sa.String(length=128), nullable=False),
    )
    op.create_table(
        'drop_picks', *_base(),
        sa.Column('drop_id', sa.String(length=64), sa.ForeignKey('drops.id'), nullable=False),
        sa.Column('campaign_id', sa.String(length=64), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('consumer_id', sa.String(length=64), sa.ForeignKey('consumers.id'), nullable=False),
        sa.Column('picked_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reference', sa.String(length=32), nullable=False, unique=True),
        sa.Column('crew_code', sa.String(length=16), nullable=True, unique=True),
        sa.Column('pass_secret', sa.String(length=64), nullable=False),
        sa.Column('fulfilment_status', sa.Enum('pending', 'sent', 'redeemed', name='drop_fulfilment'), nullable=False),
        sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        sa.Column('notified', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('drop_id', 'consumer_id', name='uq_drop_pick'),
    )
    op.create_table(
        'crew_members', *_base(),
        sa.Column('pick_id', sa.String(length=64), sa.ForeignKey('drop_picks.id'), nullable=False),
        sa.Column('drop_id', sa.String(length=64), sa.ForeignKey('drops.id'), nullable=False),
        sa.Column('consumer_id', sa.String(length=64), sa.ForeignKey('consumers.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('drop_id', 'consumer_id', name='uq_crew_member_drop'),
    )


def downgrade() -> None:
    op.drop_table('crew_members')
    op.drop_table('drop_picks')
    op.drop_table('drop_runs')
    op.drop_table('campaign_members')
    op.drop_table('drops')
    op.drop_table('campaigns')
