from sqlalchemy import Column, Integer, String, DateTime # type: ignore
from uuid import uuid4 # type: ignore
from datetime import datetime, timezone
import json

# Base = declarative_base()

fmt_time = '%Y-%m-%d %H:%M:%S'

class BaseModel:
    id = Column(String(64), primary_key=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    def __init__(self, **kwargs):
        self.id = str(uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        for key, value in kwargs.items():
            if key not in ['id', 'created_at', 'updated_at']:
                setattr(self, key, value)
        from app import db
        db.session.add(self)

    def save(self):
        from app import db
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def delete(self):
        from app import db
        db.session.delete(self)
        self.save()

    def to_json(self):
        """
            returns json representation of self
        """
        obj_dict = {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if not column.name.startswith('_')
        }
        return obj_dict

from sqlalchemy import Column, String, Integer  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from flask_appbuilder import Model  # type: ignore

from app.models.base_model import BaseModel


class Category(BaseModel, Model):
    """
    Category model definition.
    """
    __tablename__ = 'categories'
    name = Column(String(64), nullable=False, unique=True)
    slug = Column(String(64), nullable=False, unique=True)
    image_url = Column(String(128))

    # TODO: Move this later to redis for better performance optimization
    offer_count = Column(Integer, nullable=False, default=0)
    merchant_count = Column(Integer, nullable=False, default=0)

    # *Many
    merchants = relationship('Merchant', back_populates='category')
    offers = relationship('Offer', back_populates='category')

    def __str__(self):
        return f'{self.name}'
#!/usr/bin/env python3
from app.models.base_model import BaseModel
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, String, DateTime  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from flask_appbuilder import Model  # type: ignore


class Consumer(BaseModel, Model):
    """
    Consumer model definition.
    """
    __tablename__ = 'consumers'
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, unique=True)
    phone = Column(String(128), nullable=True, default=None)

    school = Column(String(128))
    graduation_year = Column(String(4))
    major = Column(String(128))
    student_id = Column(String(128))
    bio = Column(String(512), nullable=True, default=None)
    location = Column(String(128), nullable=True, default=None)
    profile_picture = Column(String(128), nullable=True, default=None)
    verified_at = Column(DateTime, nullable=True)
    _password = Column(String(256), nullable=False)

    saved_offers = relationship('SavedOffer', back_populates='consumer', cascade='all, delete-orphan')

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.id.split('-')[0]}"

    @property
    def profile_complete(self) -> float:
        """
        Check if the consumer's profile is complete.
        A profile is considered complete if all required fields are filled.
        Returns a value indicating the percentage of profile completion.
        """
        required_fields = [
            self.first_name, self.last_name, self.email, self.phone,
            self.school, self.graduation_year, self.major, self.student_id,
            self.location, self.verified
        ]
        filled_fields = sum(1 for field in required_fields if field)
        return len(required_fields) and (filled_fields / len(required_fields)) * 100 or 0.0

    # *Many
    coupons = relationship(
        'Coupon',
        back_populates='consumer',
        cascade='all, delete-orphan'
    )

    @property
    def password(self) -> str:
        """
        Getter for the password attribute.
        """
        raise AttributeError("password is not accessible")

    @password.setter
    def password(self, value: Column[str]) -> None:
        """
        Setter for the password attribute.
        """
        if not isinstance(value, str):
            raise TypeError("Password must be a string")
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self._password = generate_password_hash(value)

    @property
    def verified(self) -> bool:
        """
        Getter for the verified attribute.
        """
        return self.verified_at is not None

    def verify_password(self, password: str) -> bool:
        """
        Verify the provided password against the stored hashed password.
        """
        if not isinstance(password, str):
            raise TypeError("Password must be a string")
        return check_password_hash(str(self._password), password)
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel
from flask_appbuilder import Model  # type: ignore

COUPON_STATUS = {
    "ACTIVE": "active",
    "EXPIRED": "expired",
    "REDEEMED": "redeemed"
}


class Coupon(BaseModel, Model):
    """
    Coupon model definition.
    """
    __tablename__ = 'coupons'
    offer_id = Column(String(64), ForeignKey('offers.id'), nullable=False)
    consumer_id = Column(String(64), ForeignKey(
        'consumers.id'), nullable=False)
    redemption_location_id = Column(String(64), ForeignKey('stores.id'), nullable=True)

    coupon_code = Column(String(64), nullable=False, unique=True)
    redeemed_at = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=False)
    status: Column[Enum] = Column(Enum(*COUPON_STATUS.values()),
                                  nullable=False, default=COUPON_STATUS['ACTIVE'])
    qr_code = Column(String(128), nullable=True, default=None)
    redeemed_amount = Column(Integer, nullable=True)  # Amount saved in cents

    consumer = relationship('Consumer', back_populates='coupons')
    offer = relationship('Offer', back_populates='coupons')
    redemption_location = relationship('Store', back_populates='redeemed_coupons')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._generate_qr_code()

    def _generate_qr_code(self):
        """
        Generates a QR code for the coupon.
        """
        from app.utils import generate_qr
        self.qr_code = generate_qr(self.coupon_code)

    @property
    def expired(self):
        """
        Getter for the expired status attribute.
        """
        return self.status == COUPON_STATUS['EXPIRED']

    @property
    def redeemed(self):
        """
        Getter for the redeemed status attribute.
        """
        return self.status == COUPON_STATUS['REDEEMED']

    @property
    def active(self):
        """
        Getter for the active status attribute.
        """
        return self.status == COUPON_STATUS['ACTIVE']
from sqlalchemy import Column, String, DateTime, ForeignKey  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event

from app.models.base_model import BaseModel
from app.models.category import Category  # type: ignore
from flask_appbuilder import Model  # type: ignore


class Merchant(BaseModel, Model):
    """
    Vendor model definition.
    """
    __tablename__ = 'merchants'
    # Foreign keys
    category_id = Column(String(64), ForeignKey(
        'categories.id', ondelete='SET NULL'), nullable=True)

    # Attributes
    email = Column(String(128), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    logo = Column(String(128), nullable=True, default=None)
    website = Column(String(128), nullable=True, default=None)
    phone = Column(String(128), nullable=True, default=None)
    address = Column(String(256), nullable=True, default=None)
    city = Column(String(128), nullable=True, default=None)
    country = Column(String(128), nullable=True, default=None)
    zip_code = Column(String(16), nullable=True, default=None)
    _password = Column(String(256), nullable=False)
    preferred_currency = Column(String(8), nullable=True, default=None)
    email_verified_on = Column(DateTime, nullable=True)
    approved_on = Column(DateTime, nullable=True)

    # *One
    category = relationship('Category', back_populates='merchants')

    # *Many
    stores = relationship('Store', back_populates='merchant')
    offers = relationship(
        'Offer', back_populates='merchant')

    def __str__(self):
        return self.name

    @property
    def email_verified(self) -> bool:
        """
        Check if the merchant's email is verified.
        Returns True if email is verified, False otherwise.
        """
        return self.email_verified_on is not None

    @property
    def approved(self) -> bool:
        """
        Getter for the approved attribute.
        """
        return self.approved_on is not None

    @property
    def password(self) -> str:
        """
        Getter for the password attribute.
        """
        raise AttributeError("password is not accessible")

    @password.setter
    def password(self, value: Column[str]) -> None:
        """
        Setter for the password attribute.
        """
        if not isinstance(value, str):
            raise TypeError("Password must be a string")
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self._password = generate_password_hash(value)

    def verify_password(self, password: str) -> bool:
        """
        Verify the provided password against the stored hashed password.
        """
        if not isinstance(password, str):
            raise TypeError("Password must be a string")
        return check_password_hash(str(self._password), password)


@event.listens_for(Merchant, 'before_insert')
def increment_merchant_count(mapper, connection, target):
    """
        Increment the merchant count in the category before inserting a new merchant.
        """
    CategoryTbl = Category.__table__
    connection.execute(
        CategoryTbl.update().where(CategoryTbl.c.id == target.category_id).values(
            merchant_count=CategoryTbl.c.merchant_count + 1)
    )
from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy import event, UniqueConstraint  # type: ignore
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Enum, DateTime, CheckConstraint, Table  # type: ignore
from sqlalchemy.orm import relationship, validates  # type: ignore

from app.models.base_model import BaseModel
from app.models.merchant import Merchant  # type: ignore
from app.models.category import Category  # type: ignore
from flask_appbuilder import Model  # type: ignore
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
    "SOLD_OUT": "sold_out"
}

offer_tags = Table(
    'offer_tags', db.metadata,
    Column('offer_id', String(64), ForeignKey('offers.id'), primary_key=True),
    Column('tag_id', String(64), ForeignKey('tags.id'), primary_key=True)
)


class Tag(BaseModel, Model):
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
    coupon_limit: Column[int] = Column(Integer, nullable=False, default=1)
    status: Column[Enum] = Column(
        Enum(*OFFER_STATUS.values()),
        nullable=False, default=OFFER_STATUS["ACTIVE"])
    start_date: Column[datetime] = Column(DateTime, nullable=False,
                                          default=datetime.now(timezone.utc))
    end_date: Column[datetime] = Column(DateTime, nullable=False)
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


class OfferView(BaseModel, Model):
    """Tracks unique views of offers by users"""
    __tablename__ = 'offer_views'

    offer_id = Column(String(64), ForeignKey('offers.id'), nullable=False)
    user_id = Column(String(64), ForeignKey('consumers.id'), nullable=False)

    offer = relationship('Offer', backref='views')
    user = relationship('Consumer', backref='viewed_offers')

    __table_args__ = (
        UniqueConstraint('offer_id', 'user_id', name='unique_offer_view'),
    )


class SavedOffer(BaseModel, Model):
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
from sqlalchemy import Column, String, ForeignKey  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel
from flask_appbuilder import Model  # type: ignore


class Store(BaseModel, Model):
    __tablename__ = 'stores'
    # Foreign Keys
    merchant_id = Column(String(64), ForeignKey(
        'merchants.id'), nullable=False)

    # Attributes
    name = Column(String(32), nullable=False)
    location = Column(String(64), nullable=False)
    contact_email = Column(String(128), nullable=False)
    contact_phone = Column(String(16), nullable=True)
    manager_name = Column(String(64), nullable=True)

    # *One
    merchant = relationship(
        'Merchant', back_populates='stores')
    redeemed_coupons = relationship(
        'Coupon', back_populates='redemption_location')
