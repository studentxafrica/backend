from datetime import datetime, timezone
from sqlalchemy import func  # type: ignore
from app import db
from app.models.offer import Offer, OfferView
from app.models.coupon import Coupon


def track_offer_view(offer_id, user_id=None):
    """
    Track when an offer is viewed
    """
    offer: Offer = db.session.query(Offer).filter(Offer.id == offer_id).first() # type: ignore
    if not offer:
        return
    if not offer.view_count:
        offer.view_count = 0
    offer.view_count += 1
    if user_id:
        # Check if this is a unique visitor
        view: OfferView = db.session.query(OfferView).filter(
            OfferView.offer_id == offer_id,
            OfferView.user_id == user_id
        ).first() # type: ignore

        if not view:
            if not offer.unique_visitors:
                offer.unique_visitors = 0
            offer.unique_visitors += 1
            new_view = OfferView(
                offer_id=offer_id,
                user_id=user_id
            )
            new_view.save()

    offer.last_viewed_at = datetime.now(tz=timezone.utc)
    offer.save()


def track_coupon_redemption(coupon_id):
    """Track when a coupon is redeemed and calculate redemption time"""
    coupon: Coupon = db.session.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        return

    offer: Offer = coupon.offer
    if not offer:
        return

    # Calculate redemption time in hours
    redemption_time = (
        datetime.now() - coupon.created_at).total_seconds() / 3600

    # Update average redemption time
    if offer.avg_redemption_time_hours:
        total_redemptions = db.session.query(func.count(Coupon.id)).filter(
            Coupon.offer_id == offer.id,
            Coupon.status == 'redeemed'
        ).scalar()

        offer.avg_redemption_time_hours = (
            (offer.avg_redemption_time_hours * total_redemptions) + redemption_time
        ) / (total_redemptions + 1)
    else:
        offer.avg_redemption_time_hours = redemption_time
    offer.save()
