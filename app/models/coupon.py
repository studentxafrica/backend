from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel
from app import db  # type: ignore

COUPON_STATUS = {
    "ACTIVE": "active",
    "EXPIRED": "expired",
    "REDEEMED": "redeemed"
}


class Coupon(BaseModel, db.Model):
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
