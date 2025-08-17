# Utility function to expire offers that are past their end date.
from typing import List

from app.models.offer import Offer
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
        elif offer.coupon_limit - len(offer.coupons) <= 0:
            offer.status = 'sold_out'
        else:
            offer.status = 'active'
        offer.save()
