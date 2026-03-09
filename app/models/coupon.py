from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey, UniqueConstraint, Computed  # type: ignore
from sqlalchemy.orm import relationship, mapped_column, Mapped  # type: ignore

from app.models.base_model import BaseModel
from app import db  # type: ignore
from datetime import datetime

COUPON_STATUS: dict[str, str] = {
    "ACTIVE": "active",
    "EXPIRED": "expired",
    "REDEEMED": "redeemed",
    "REVOKED": "revoked"
}


class Coupon(BaseModel, db.Model):
    """
    Coupon model definition.
    """
    __tablename__ = 'coupons'
    offer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('offers.id'), nullable=False)
    consumer_id: Mapped[str | None] = mapped_column(String(64), ForeignKey(
        'consumers.id'), nullable=True)
    active_consumer_id: Mapped[str | None] = mapped_column(
        String(64),
        Computed(
            "CASE WHEN status = 'active' THEN consumer_id ELSE NULL END",
            persisted=True
        )
    )
    redemption_location_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey('stores.id'), nullable=True)

    coupon_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(Enum(*COUPON_STATUS.values()),
                                        nullable=False, default=COUPON_STATUS['ACTIVE'])
    qr_code: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None)
    redeemed_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True)  # Amount saved in cents

    consumer = relationship('Consumer', back_populates='coupons')
    offer = relationship('Offer', back_populates='coupons')
    redemption_location = relationship(
        'Store', back_populates='redeemed_coupons')

    __table_args__ = (
        UniqueConstraint(
            "offer_id",
            "active_consumer_id",
            name="uq_coupons_offer_active_consumer"
        ),
    )

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
        return bool(self.status == COUPON_STATUS['REDEEMED'])

    @property
    def active(self):
        """
        Getter for the active status attribute.
        """
        return self.status == COUPON_STATUS['ACTIVE']

    @property
    def revoked(self):
        """
        Getter for the revoked status attribute.
        """
        return self.status == COUPON_STATUS['REVOKED']
