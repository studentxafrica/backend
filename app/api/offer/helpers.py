from datetime import datetime, timezone
from typing import Tuple
from urllib.parse import urlparse
from sqlalchemy import func  # type: ignore
from app import db
from app.models.offer import (
    Offer, OfferView, DISCOUNT_TYPES, USAGE_TYPES, OFFER_KINDS
)
from app.models.coupon import Coupon


def is_valid_event_url(url) -> bool:
    """
    Check that an event link is a usable http(s) address.
    """
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def serialize_claim(offer: Offer, coupon: Coupon) -> dict:
    """
    Build the payload a student sees after claiming an offer.

    Discount offers hand out the code that was generated for that student.
    Event offers hand out the event link and its QR code, which are the same
    for everyone who claims the offer, so no code is exposed.
    """
    payload = {
        'offerKind': offer.offer_kind,
        'code': None if offer.is_event else coupon.coupon_code,
        'qrCode': coupon.qr_code,
        'expiryDate': coupon.expiry_date,
        'status': coupon.status,
    }
    if offer.is_event:
        payload['eventUrl'] = offer.event_url
    return payload


def prepare_offer_fields(data: dict) -> Tuple[dict | None, Tuple[dict, int] | None]:
    """
    Validate an offer payload and turn it into keyword arguments for Offer.

    Shared by merchants creating their own offers and admins creating offers on
    a merchant's behalf, so both routes apply exactly the same rules.

    Returns (fields, error) where error is a (body, status_code) pair.
    """
    offer_kind = data.get('offer_kind') or OFFER_KINDS["DISCOUNT"]
    if offer_kind not in OFFER_KINDS.values():
        return None, ({
            "message": f"Invalid offer_kind. Must be one of: {list(OFFER_KINDS.values())}"
        }, 400)
    is_event = offer_kind == OFFER_KINDS["EVENT"]

    if is_event:
        required_fields = [
            'title', 'description', 'slug', 'cover_image', 'event_url',
            'coupon_limit', 'start_date', 'end_date'
        ]
    else:
        required_fields = [
            'title', 'description', 'slug', 'cover_image', 'discount_type',
            'discount_value' if data.get('discount_type') in [
                'percentage', 'fixed'] else None,
            'currency', 'coupon_limit', 'redemption_type',
            'start_date', 'end_date'
        ]

    def _missing(field_name: str) -> bool:
        if field_name not in data:
            return True
        value = data.get(field_name)
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    for field in required_fields:
        if field is not None and _missing(field):
            return None, ({"message": f"Missing required field: {field}"}, 400)

    # Upload the cover image if it arrived as a file path or base64 payload
    import cloudinary.uploader  # type: ignore
    cover_image = data['cover_image']
    if not cover_image.startswith('http'):
        upload_result = cloudinary.uploader.upload(cover_image, folder='offers/')
        cover_image = upload_result['secure_url']

    usage_type = data.get('usage_type') or USAGE_TYPES["SINGLE_USE"]
    if usage_type not in USAGE_TYPES.values():
        return None, ({
            "message": f"Invalid usage_type. Must be one of: {list(USAGE_TYPES.values())}"
        }, 400)
    if usage_type == USAGE_TYPES["TIERED"]:
        return None, ({"message": "Tiered offers are not supported"}, 400)
    if usage_type == USAGE_TYPES["MULTI_USE"] and not data.get('max_claims_per_user'):
        return None, ({
            "message": "max_claims_per_user is required for multi_use offers"
        }, 400)

    discount_type = data.get('discount_type')
    discount_value = data.get('discount_value')
    currency = data.get('currency')
    event_url = None
    event_qr_code = None

    if is_event:
        # A student registers for an event once, and the link they receive is
        # the same one everyone else receives.
        if usage_type != USAGE_TYPES["SINGLE_USE"]:
            return None, ({
                "message": "Event offers can only be registered for once per student"
            }, 400)
        if not is_valid_event_url(data.get('event_url')):
            return None, ({
                "message": "Invalid event_url. Provide a link starting with http:// or https://"
            }, 400)
        event_url = data['event_url'].strip()
        # Generated once so every registration shares the same QR code
        from app.utils import generate_qr
        event_qr_code = generate_qr(event_url)
        # An event grants access rather than money off a purchase
        discount_type = DISCOUNT_TYPES["FREE_ITEM"]
        discount_value = 0
        currency = currency or 'USD'

    return {
        'title': data.get('title'),
        'description': data.get('description'),
        'slug': data.get('slug'),
        'cover_image': cover_image,
        'offer_kind': offer_kind,
        'event_url': event_url,
        'event_qr_code': event_qr_code,
        'discount_type': discount_type,
        'discount_value': discount_value,
        'currency': currency,
        'coupon_limit': data.get('coupon_limit'),
        'start_date': datetime.fromisoformat(data.get('start_date')),
        'end_date': datetime.fromisoformat(data.get('end_date')),
        'terms_and_conditions': data.get('terms_and_conditions', ''),
        'usage_type': usage_type,
        'max_claims_per_user': data.get('max_claims_per_user', 1),
        'cooldown_period_hours': data.get('cooldown_period_hours'),
        'tier_progression': data.get('tier_progression'),
    }, None


def apply_event_url_update(offer: Offer, data: dict) -> Tuple[dict, int] | None:
    """
    Update an event offer's link, if the payload carries one.

    Regenerates the shared QR code and points every registration already handed
    out at the new one, so the whole cohort keeps seeing the same thing.
    Returns an error pair on invalid input, otherwise None.
    """
    if not data.get('event_url'):
        return None

    if not offer.is_event:
        return {"message": "An event link can only be set on event offers"}, 400

    if not is_valid_event_url(data['event_url']):
        return {
            "message": "Invalid event link. Provide a link starting with http:// or https://"
        }, 400

    event_url = data['event_url'].strip()
    if event_url != offer.event_url:
        from app.utils import generate_qr
        offer.event_url = event_url
        offer.event_qr_code = generate_qr(event_url)
        db.session.query(Coupon).filter(Coupon.offer_id == offer.id).update(
            {Coupon.qr_code: offer.event_qr_code}, synchronize_session=False)
    return None


def serialize_offer_for_admin(offer: Offer) -> dict:
    """
    Offer payload for the admin portal's offer list and detail view.
    """
    coupons = offer.coupons or []
    claimed = len([c for c in coupons if c.status == 'active'])
    redeemed = len([c for c in coupons if c.status == 'redeemed'])
    return {
        'id': offer.id,
        'title': offer.title,
        'description': offer.description,
        'slug': offer.slug,
        'merchant': {
            'id': offer.merchant.id,
            'name': offer.merchant.name,
            'logo': offer.merchant.logo,
        } if offer.merchant else None,
        'category': {
            'id': offer.category.id,
            'name': offer.category.name,
        } if offer.category else None,
        'offerKind': offer.offer_kind,
        'eventUrl': offer.event_url,
        'discountType': offer.discount_type,
        'discountValue': offer.discount_value,
        'currency': offer.currency,
        'redemptionType': offer.redemption_type,
        'couponLimit': offer.coupon_limit,
        'claimed': claimed,
        'redeemed': redeemed,
        'usage_type': offer.usage_type,
        'max_claims_per_user': offer.max_claims_per_user,
        'cooldown_period_hours': offer.cooldown_period_hours,
        'startDate': offer.start_date.isoformat(),
        'endDate': offer.end_date.isoformat(),
        'status': offer.status,
        'revenue': sum(c.redeemed_amount or 0 for c in coupons) / 100,
        'views': offer.view_count or 0,
        'coverImage': offer.cover_image,
        'termsAndConditions': offer.terms_and_conditions,
    }


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
