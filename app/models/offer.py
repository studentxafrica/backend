from datetime import datetime, timezone
from sqlalchemy import event  # type: ignore
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Enum, DateTime, CheckConstraint  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel
from app.models.category import Category  # type: ignore
from flask_appbuilder import Model  # type: ignore

DISCOUNT_TYPES = {
    "PERCENTAGE": "percentage",
    "FIXED_AMOUNT": "fixed_amount",
    "BUY_ONE_GET_ONE": "buy_one_get_one",
    "FREE_ITEM": "free_item"
}

OFFER_STATUS = {
    "ACTIVE": "active",
    "INACTIVE": "inactive",
    "EXPIRED": "expired",
    "SOLD_OUT": "sold_out"
}


class Offer(BaseModel, Model):
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
    title = Column(String(64), nullable=False)
    description = Column(String(256), nullable=False)
    slug = Column(String(64), nullable=False, unique=True)
    cover_image = Column(String(128), nullable=False)
    discount_type: Column[Enum] = Column(
        Enum(*DISCOUNT_TYPES.values()), nullable=False)
    discount_value = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    coupon_limit = Column(Integer, nullable=False, default=1)
    status: Column[Enum] = Column(
        Enum(*OFFER_STATUS.values()),
        nullable=False, default=OFFER_STATUS["ACTIVE"])
    start_date = Column(DateTime, nullable=False,
                        default=datetime.now(timezone.utc))
    end_date = Column(DateTime, nullable=False)
    terms_and_conditions = Column(Text, nullable=True)
    featured_until = Column(DateTime, nullable=True)
    highlighted_until = Column(DateTime, nullable=True)

    # *One
    merchant = relationship('Merchant', back_populates='offers')
    category = relationship('Category', back_populates='offers')

    # *Many
    coupons = relationship('Coupon', back_populates='offer')

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
