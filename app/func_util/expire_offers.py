# Utility function to expire offers that are past their end date.
from typing import List

from app.models.offer import Offer, USAGE_TYPES
from app.models.coupon import Coupon, COUPON_STATUS
from app import db


def expire_offers():
    offers: List[Offer] = db.session.query(Offer).filter(
        Offer.end_date < db.func.now()).all()
    for offer in offers:
        offer.status = 'expired'
        offer.save()


def update_status():
    now = db.session.execute(db.func.now()).scalar()
    offers: List[Offer] = db.session.query(Offer).filter(
        Offer.status != 'inactive'
    ).all()
    for offer in offers:
        if offer.end_date < now:
            offer.status = 'expired'
        elif offer.usage_type != USAGE_TYPES["UNLIMITED"]:
            coupon_limit = offer.coupon_limit or 0
            claimed_redeemed = db.session.query(db.func.count(Coupon.id)).filter(
                Coupon.offer_id == offer.id,
                Coupon.status.in_(
                    [COUPON_STATUS["ACTIVE"], COUPON_STATUS["REDEEMED"]]
                )
            ).scalar() or 0
            if coupon_limit <= 0 or claimed_redeemed >= coupon_limit:
                offer.status = 'sold_out'
            else:
                offer.status = 'active'
        else:
            offer.status = 'active'
        offer.save()
