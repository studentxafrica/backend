"""
Campaigns of perks that StudentX gives to its verified members.

A campaign (such as StudentXmas) has a schedule of drops. Verified students
join the campaign once, and each drop's recipients are picked at random from
the members on the drop's pick time. Brands appear only as the perk; they
have no account and no part in running the campaign.
"""
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.models.base_model import BaseModel

DROP_KINDS = {"AIRTIME": "airtime", "VOUCHER": "voucher", "CREW": "crew"}
DROP_STATUS = {"UPCOMING": "upcoming", "PICKED": "picked"}
FULFILMENT_STATUS = {"PENDING": "pending", "SENT": "sent", "REDEEMED": "redeemed"}


class Campaign(BaseModel, db.Model):
    __tablename__ = "campaigns"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Members agree to this version of the campaign terms when they join.
    terms_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # How many drops one member can be picked for over the whole campaign.
    max_picks_per_member: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    drops = relationship("Drop", back_populates="campaign", order_by="Drop.pick_at")


class Drop(BaseModel, db.Model):
    __tablename__ = "drops"

    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    # The brand shown as the perk, e.g. "Safaricom". Not a sponsor.
    brand: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Photo of the perk itself (not a brand logo). Optional.
    cover_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    kind: Mapped[str] = mapped_column(Enum(*DROP_KINDS.values(), name="drop_kind"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Crew perks: how many people one pass covers, the picked member included.
    crew_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pick_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    use_within_days: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    status: Mapped[str] = mapped_column(
        Enum(*DROP_STATUS.values(), name="drop_status"), nullable=False, default=DROP_STATUS["UPCOMING"])
    # Hash of the PIN the venue uses to mark passes as used.
    _venue_pin: Mapped[str | None] = mapped_column("venue_pin_hash", String(256), nullable=True)

    campaign = relationship("Campaign", back_populates="drops")
    picks = relationship("DropPick", back_populates="drop")
    run = relationship("DropRun", back_populates="drop", uselist=False)

    @property
    def is_crew(self) -> bool:
        return self.kind == DROP_KINDS["CREW"]


class CampaignMember(BaseModel, db.Model):
    """A verified student who joined a campaign, and so is in its drops."""
    __tablename__ = "campaign_members"
    __table_args__ = (UniqueConstraint("campaign_id", "consumer_id", name="uq_campaign_member"),)

    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id"), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(64), ForeignKey("consumers.id"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    terms_version: Mapped[str] = mapped_column(String(32), nullable=False)

    consumer = relationship("Consumer")


class DropRun(BaseModel, db.Model):
    """The record of one drop's random pick, kept so it can be shown to be fair."""
    __tablename__ = "drop_runs"

    drop_id: Mapped[str] = mapped_column(String(64), ForeignKey("drops.id"), nullable=False, unique=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    picked_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Perks left unawarded because fewer members were eligible than the quantity.
    shortfall: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # SHA-256 of the sorted IDs of every eligible member, so the pool can be audited.
    eligible_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(128), nullable=False)

    drop = relationship("Drop", back_populates="run")


class DropPick(BaseModel, db.Model):
    """A member picked for a drop."""
    __tablename__ = "drop_picks"
    __table_args__ = (
        UniqueConstraint("drop_id", "consumer_id", name="uq_drop_pick"),
    )

    drop_id: Mapped[str] = mapped_column(String(64), ForeignKey("drops.id"), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id"), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(64), ForeignKey("consumers.id"), nullable=False)
    picked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Voucher or booking reference shown on the pass.
    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    # Code shared with friends to join a crew perk.
    crew_code: Mapped[str | None] = mapped_column(String(16), nullable=True, unique=True)
    # Secret the rotating pass code is derived from. Never sent to the browser.
    _pass_secret: Mapped[str] = mapped_column("pass_secret", String(64), nullable=False)
    fulfilment_status: Mapped[str] = mapped_column(
        Enum(*FULFILMENT_STATUS.values(), name="drop_fulfilment"), nullable=False,
        default=FULFILMENT_STATUS["PENDING"])
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    drop = relationship("Drop", back_populates="picks")
    consumer = relationship("Consumer")
    crew = relationship("CrewMember", back_populates="pick", order_by="CrewMember.joined_at")


class CrewMember(BaseModel, db.Model):
    """A friend a picked member brings along on a crew perk."""
    __tablename__ = "crew_members"
    __table_args__ = (
        UniqueConstraint("drop_id", "consumer_id", name="uq_crew_member_drop"),
    )

    pick_id: Mapped[str] = mapped_column(String(64), ForeignKey("drop_picks.id"), nullable=False)
    drop_id: Mapped[str] = mapped_column(String(64), ForeignKey("drops.id"), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(64), ForeignKey("consumers.id"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    pick = relationship("DropPick", back_populates="crew")
    consumer = relationship("Consumer")
