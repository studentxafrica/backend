from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy import event, UniqueConstraint  # type: ignore
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Enum, DateTime, CheckConstraint, Table, JSON, Constraint  # type: ignore
from sqlalchemy.orm import relationship, validates, Mapped, mapped_column  # type: ignore

from app.models.base_model import BaseModel
from app.models.merchant import Merchant  # type: ignore
from app.models.category import Category  # type: ignore
from app import db

DISCOUNT_TYPES: Dict[str, str] = {
    "PERCENTAGE": "percentage",
    "FIXED_AMOUNT": "fixed_amount",
    "BUY_ONE_GET_ONE": "buy_one_get_one",
    "FREE_ITEM": "free_item"
}

OFFER_STATUS: Dict[str, str] = {
    "ACTIVE": "active",
    "INACTIVE": "inactive",
    "EXPIRED": "expired",
    "SOLD_OUT": "sold_out",
    "SUSPENDED": 'suspended'
}

USAGE_TYPES: Dict[str, str] = {
    "SINGLE_USE": "single_use",
    "MULTI_USE": "multi_use",
    "UNLIMITED": "unlimited",
    "TIERED": "tiered"
}

# What a claim entitles the student to: a discount code, or access to an event.
OFFER_KINDS: Dict[str, str] = {
    "DISCOUNT": "discount",
    "EVENT": "event"
}

offer_tags = Table(
    'offer_tags', db.metadata,
    Column('offer_id', String(64), ForeignKey('offers.id'), primary_key=True),
    Column('tag_id', String(64), ForeignKey('tags.id'), primary_key=True)
)


class Tag(BaseModel, db.Model):
    """
    Tag model definition.
    """
    __tablename__ = 'tags'
    # id = mapped_column(String(64), primary_key=True)
    name = mapped_column(String(64), nullable=False, unique=True)

    offers = relationship('Offer', secondary=offer_tags, back_populates='tags')

    @validates('name')
    def validate_name(self, key, value):
        """
        Validate the tag name to ensure it is lowercase
        """
        return value.lower().strip()

    def __str__(self):
        return self.name


class Offer(BaseModel, db.Model):
    """
    CouponDeal model definition.
    """
    __tablename__ = 'offers'
    # Foreign Keys
    merchant_id: Mapped[str] = mapped_column(String(64), ForeignKey(
        'merchants.id'), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(64), ForeignKey(
        'categories.id', ondelete='SET NULL'), nullable=True)

    # Attributes
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    cover_image: Mapped[str] = mapped_column(String(256), nullable=False)
    offer_kind: Mapped[str] = mapped_column(
        Enum(*OFFER_KINDS.values()), nullable=False,
        server_default=OFFER_KINDS["DISCOUNT"], default=OFFER_KINDS["DISCOUNT"])
    # Where the event happens (meeting link, ticket page, ...). Event offers only.
    event_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # QR of event_url, generated once and shared by every claim on the offer.
    event_qr_code: Mapped[str | None] = mapped_column(
        String(256), nullable=True)
    discount_type: Mapped[str] = mapped_column(
        Enum(*DISCOUNT_TYPES.values()), nullable=False)
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    redemption_type: Mapped[str] = mapped_column(
        Enum("in-store", "online", "both"), nullable=False, default="both")
    coupon_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=0)
    status: Mapped[str] = mapped_column(
        Enum(*OFFER_STATUS.values()),
        nullable=False, default=OFFER_STATUS["ACTIVE"])
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                 default=datetime.now(timezone.utc), index=True)
    end_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True)
    terms_and_conditions: Mapped[str |
                                 None] = mapped_column(Text, nullable=True)
    featured_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    highlighted_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    tags = relationship('Tag', secondary=offer_tags, back_populates='offers')

    view_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    last_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    # in cents to avoid floating point issues
    revenue_generated: Mapped[int] = mapped_column(Integer, default=0)
    # Average time from claim to redemption in hours
    avg_redemption_time_hours: Mapped[int | None] = mapped_column(
        Integer, nullable=True)

    # New flexible usage system fields
    usage_type: Mapped[str] = mapped_column(
        Enum(*USAGE_TYPES.values()),
        nullable=False, default=USAGE_TYPES["SINGLE_USE"])
    max_claims_per_user: Mapped[int] = mapped_column(
        Integer, nullable=True, default=1)
    cooldown_period_hours: Mapped[int | None] = mapped_column(
        Integer, nullable=True)
    tier_progression: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True)  # JSON for tiered discount rules

    # *One
    merchant: Mapped[Merchant] = relationship(
        'Merchant', back_populates='offers')
    category: Mapped[Category] = relationship(
        'Category', back_populates='offers')

    # *Many
    coupons = relationship('Coupon', back_populates='offer',
                           cascade='all, delete-orphan')
    saved_offers = relationship(
        'SavedOffer', back_populates='offer', cascade='all, delete-orphan')
    views = relationship('OfferView', backref='offer',
                         cascade='all, delete-orphan')
    user_usage_stats = relationship(
        'UserOfferUsage', back_populates='offer', cascade='all, delete-orphan')

    # Constraints
    __table_args__ = (
        CheckConstraint('end_date > start_date', name='check_end_after_start'),
        CheckConstraint('featured_until > start_date',
                        name='check_featured_after_start'),
        CheckConstraint('highlighted_until > start_date',
                        name='check_highlighted_after_start'),
        CheckConstraint('end_date > featured_until',
                        name='check_end_after_featured'),
        CheckConstraint('end_date > highlighted_until',
                        name='check_end_after_highlighted'),
        CheckConstraint('featured_until > highlighted_until',
                        name='check_featured_after_highlighted'),
    )

    def __str__(self):
        return f"{self.title} - {self.id.split('-')[0]}"

    # @property
    # def status(self):
    #     """
    #     Getter for the status attribute.
    #     """
    #     end_date = self.end_date
    #     if end_date.tzinfo is None:
    #         end_date = end_date.replace(tzinfo=timezone.utc)
    #     if end_date < datetime.now(timezone.utc):
    #         return OFFER_STATUS["EXPIRED"]
    #     if self.coupon_limit <= 0:
    #         return OFFER_STATUS["SOLD_OUT"]
    #     if self._status == OFFER_STATUS["INACTIVE"]:
    #         return OFFER_STATUS["INACTIVE"]
    #     print(OFFER_STATUS["ACTIVE"])
    #     return OFFER_STATUS["ACTIVE"]

    # @status.setter
    # def status(self, value):
    #     """
    #     Setter for the status attribute.
    #     """
    #     if value not in OFFER_STATUS.values():
    #         raise ValueError(f"Invalid status: {value}")
    #     self._status = value

    @property
    def is_event(self):
        """
        Whether claiming this offer grants access to an event instead of a discount code.
        """
        return self.offer_kind == OFFER_KINDS["EVENT"]

    def ensure_event_qr_code(self):
        """
        Generate the shared QR code for the event link if it is missing.
        Every claim on the offer hands out this same QR code.
        """
        if self.is_event and self.event_url and not self.event_qr_code:
            from app.utils import generate_qr
            self.event_qr_code = generate_qr(self.event_url)
        return self.event_qr_code

    @property
    def featured(self):
        """
        Getter for the featured status attribute.
        """
        return self.featured_until is not None

    @property
    def highlighted(self):
        """
        Getter for the highlighted status attribute.
        """
        return self.highlighted_until is not None


@event.listens_for(Offer, 'before_insert')
def increment_category_offer_count(mapper, connection, target):
    """
    Increment the offer count for the associated merchant before inserting a new offer.
    """
    from app.models.merchant import Merchant  # type: ignore
    from sqlalchemy import select  # type: ignore

    if target.merchant_id is None:
        return

    # Get merchant's category_id directly from database
    merchant_table = Merchant.__table__  # type: ignore
    merchant = connection.execute(
        select(merchant_table.c.category_id)
        .where(merchant_table.c.id == target.merchant_id)
    ).fetchone()

    if merchant and merchant.category_id:
        categoryTable = Category.__table__  # type: ignore
        connection.execute(
            categoryTable.update()
            .where(categoryTable.c.id == merchant.category_id)
            .values(offer_count=categoryTable.c.offer_count + 1)
        )


@event.listens_for(Offer, 'before_delete')
def decrement_category_offer_count(mapper, connection, target):
    """
    Decrement the offer count for the associated merchant before deleting an offer.
    """
    categoryTable = Category.__table__  # type: ignore
    connection.execute(
        categoryTable.update().where(categoryTable.c.id == target.merchant.category_id).values(
            offer_count=categoryTable.c.offer_count - 1)
    )


class OfferView(BaseModel, db.Model):
    """Tracks unique views of offers by users"""
    __tablename__ = 'offer_views'

    offer_id = mapped_column(
        String(64), ForeignKey('offers.id'), nullable=False)
    user_id = mapped_column(String(64), ForeignKey(
        'consumers.id'), nullable=False)

    user = relationship('Consumer', backref='viewed_offers')

    __table_args__ = (
        UniqueConstraint('offer_id', 'user_id', name='unique_offer_view'),
    )


class SavedOffer(BaseModel, db.Model):
    """
    SavedOffer model definition.
    """
    __tablename__ = 'saved_offers'
    # Foreign Keys
    consumer_id = mapped_column(String(64), ForeignKey(
        'consumers.id'), nullable=False)
    offer_id = mapped_column(String(64), ForeignKey(
        'offers.id'), nullable=False)

    # *One
    consumer = relationship('Consumer', back_populates='saved_offers')
    offer = relationship('Offer', back_populates='saved_offers')

    __table_args__ = (
        CheckConstraint('consumer_id IS NOT NULL',
                        name='check_consumer_id_not_null'),
        CheckConstraint('offer_id IS NOT NULL',
                        name='check_offer_id_not_null'),
    )
