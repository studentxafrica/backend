from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy import event, UniqueConstraint  # type: ignore
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Enum, DateTime, CheckConstraint, Table, JSON  # type: ignore
from sqlalchemy.orm import relationship, validates  # type: ignore

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

OFFER_STATUS = {
    "ACTIVE": "active",
    "INACTIVE": "inactive",
    "EXPIRED": "expired",
    "SOLD_OUT": "sold_out",
    "SUSPENDED": 'suspended'
}

USAGE_TYPES = {
    "SINGLE_USE": "single_use",
    "MULTI_USE": "multi_use", 
    "UNLIMITED": "unlimited",
    "TIERED": "tiered"
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
    id = Column(String(64), primary_key=True)
    name = Column(String(64), nullable=False, unique=True)

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
    merchant_id = Column(String(64), ForeignKey(
        'merchants.id'), nullable=False)
    category_id = Column(String(64), ForeignKey(
        'categories.id', ondelete='SET NULL'), nullable=True)

    # Attributes
    title: Column[str] = Column(String(64), nullable=False)
    description: Column[str] = Column(String(256), nullable=False)
    slug: Column[str] = Column(String(64), nullable=False, unique=True)
    cover_image: Column[str] = Column(String(256), nullable=False)
    discount_type: Column[Enum] = Column(
        Enum(*DISCOUNT_TYPES.values()), nullable=False)
    discount_value: Column[int] = Column(Integer, nullable=False)
    currency: Column[str] = Column(String(3), nullable=False)
    redemption_type: Column[Enum] = Column(
        Enum("in-store", "online", "both"), nullable=False, default="both")
    coupon_limit: Column[int] = Column(Integer, nullable=True, default=0)
    status: Column[Enum] = Column(
        Enum(*OFFER_STATUS.values()),
        nullable=False, default=OFFER_STATUS["ACTIVE"])
    start_date: Column[datetime] = Column(DateTime, nullable=False,
                                          default=datetime.now(timezone.utc), index=True)
    end_date: Column[datetime] = Column(DateTime, nullable=False, index=True)
    terms_and_conditions = Column(Text, nullable=True)
    featured_until: Column[datetime] = Column(DateTime, nullable=True)
    highlighted_until: Column[datetime] = Column(DateTime, nullable=True)
    tags = relationship('Tag', secondary=offer_tags, back_populates='offers')

    view_count = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    last_viewed_at = Column(DateTime, nullable=True)
    # in cents to avoid floating point issues
    revenue_generated = Column(Integer, default=0)
    # Average time from claim to redemption in hours
    avg_redemption_time_hours = Column(Integer, nullable=True)

    # New flexible usage system fields
    usage_type: Column[Enum] = Column(
        Enum(*USAGE_TYPES.values()),
        nullable=False, default=USAGE_TYPES["SINGLE_USE"])
    max_claims_per_user: Column[int] = Column(Integer, nullable=True, default=1)
    cooldown_period_hours: Column[int] = Column(Integer, nullable=True)
    tier_progression: Column[Text] = Column(JSON, nullable=True)  # JSON for tiered discount rules

    # *One
    merchant: Merchant = relationship('Merchant', back_populates='offers')
    category: Category = relationship('Category', back_populates='offers')

    # *Many
    coupons = relationship('Coupon', back_populates='offer')
    saved_offers = relationship(
        'SavedOffer', back_populates='offer')

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
                        name='check_featured_after_highlighted')
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
    merchant = connection.execute(
        select([Merchant.__table__.c.category_id])
        .where(Merchant.__table__.c.id == target.merchant_id)
    ).fetchone()

    if merchant and merchant.category_id:
        categoryTable = Category.__table__
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
    categoryTable = Category.__table__
    connection.execute(
        categoryTable.update().where(categoryTable.c.id == target.merchant.category_id).values(
            offer_count=categoryTable.c.offer_count - 1)
    )
    


class OfferView(BaseModel, db.Model):
    """Tracks unique views of offers by users"""
    __tablename__ = 'offer_views'

    offer_id = Column(String(64), ForeignKey('offers.id'), nullable=False)
    user_id = Column(String(64), ForeignKey('consumers.id'), nullable=False)

    offer = relationship('Offer', backref='views')
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
    consumer_id = Column(String(64), ForeignKey(
        'consumers.id'), nullable=False)
    offer_id = Column(String(64), ForeignKey(
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
