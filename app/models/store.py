from sqlalchemy import Column, String, ForeignKey  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel
from app import db  # type: ignore


class Store(BaseModel, db.Model):
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
