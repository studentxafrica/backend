"""
Helper functions for flexible usage system validation and management.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import func  # type: ignore
from app.models.coupon import Coupon, COUPON_STATUS
from app.models.user_offer_usage import UserOfferUsage
from app.models.offer import Offer, USAGE_TYPES
from app import db


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _count_claimed_and_redeemed(offer_id: str) -> int:
    return db.session.query(func.count(Coupon.id)).filter(
        Coupon.offer_id == offer_id,
        Coupon.status.in_(
            [COUPON_STATUS["ACTIVE"], COUPON_STATUS["REDEEMED"]]
        )
    ).scalar() or 0


def get_or_create_user_usage(
    consumer_id: str,
    offer_id: str,
    *,
    create_if_missing: bool = True,
    commit: bool = True
) -> Optional[UserOfferUsage]:
    """
    Get existing user usage record or create a new one.

    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer

    Returns:
        Optional[UserOfferUsage]: The usage record if found or created
    """
    usage = db.session.query(UserOfferUsage).filter(
        UserOfferUsage.consumer_id == consumer_id,
        UserOfferUsage.offer_id == offer_id
    ).first()

    if not usage and create_if_missing:
        usage = UserOfferUsage(
            consumer_id=consumer_id,
            offer_id=offer_id,
            usage_count=0,
            total_savings=0,
            total_redemptions=0
        )
        if commit:
            usage.save()
        else:
            db.session.flush()

    return usage


def evaluate_claim_rules(
    offer: Offer,
    usage: Optional[UserOfferUsage],
    has_active_coupon: bool,
    claimed_redeemed_count: Optional[int],
    now: Optional[datetime] = None
) -> Tuple[bool, str]:
    now = now or datetime.now(timezone.utc)

    if offer.usage_type == USAGE_TYPES["TIERED"]:
        return False, "Tiered offers are not supported"
    if offer.usage_type not in [
        USAGE_TYPES["SINGLE_USE"],
        USAGE_TYPES["MULTI_USE"],
        USAGE_TYPES["UNLIMITED"]
    ]:
        return False, "Unknown usage type"

    sold_out_message = "Event is fully booked" if offer.is_event else "Coupons sold out"

    if offer.status == 'sold_out':
        return False, sold_out_message
    if offer.status != 'active':
        return False, "Offer is not active"

    end_date = _ensure_utc(offer.end_date)
    if end_date <= now:
        return False, "Offer has expired"

    if has_active_coupon:
        return False, ("You are already registered for this event" if offer.is_event
                       else "You already have an active coupon for this offer")

    # Check coupon availability for non-unlimited offers
    if offer.usage_type != USAGE_TYPES["UNLIMITED"]:
        coupon_limit = offer.coupon_limit or 0
        if coupon_limit <= 0:
            return False, sold_out_message
        if claimed_redeemed_count is None:
            return False, "Coupon availability unavailable"
        if claimed_redeemed_count >= coupon_limit:
            return False, sold_out_message

    usage_count = usage.usage_count if usage else 0
    last_claimed_at = usage.last_claimed_at if usage else None

    if offer.usage_type == USAGE_TYPES["SINGLE_USE"]:
        if usage_count > 0:
            return False, ("You have already registered for this event" if offer.is_event
                           else "You have already claimed a coupon for this offer")
        return True, ""

    if offer.usage_type == USAGE_TYPES["MULTI_USE"]:
        max_claims = offer.max_claims_per_user or 0
        if max_claims <= 0:
            return False, "Offer configuration invalid"
        if usage_count >= max_claims:
            return False, f"Maximum claims per user ({max_claims}) reached"

    # Cooldown check for multi-use and unlimited
    if last_claimed_at and offer.cooldown_period_hours:
        time_since_last = now - _ensure_utc(last_claimed_at)
        cooldown_seconds = offer.cooldown_period_hours * 3600
        if time_since_last.total_seconds() < cooldown_seconds:
            remaining_hours = (cooldown_seconds -
                               time_since_last.total_seconds()) / 3600
            return False, f"Cooldown period active. Try again in {remaining_hours:.1f} hours"

    return True, ""


def can_user_claim_offer(consumer_id: str, offer_id: str) -> Tuple[bool, str]:
    """
    Check if a user can claim a coupon for an offer based on usage rules.

    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer

    Returns:
        Tuple[bool, str]: (can_claim, reason_if_cannot)
    """
    offer = db.session.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        return False, "Offer not found"

    now = datetime.now(timezone.utc)
    usage = get_or_create_user_usage(
        consumer_id, offer_id, create_if_missing=False)

    existing_coupon = db.session.query(Coupon).filter(
        Coupon.offer_id == offer.id,
        Coupon.consumer_id == consumer_id,
        Coupon.status == COUPON_STATUS["ACTIVE"],
        Coupon.expiry_date > now
    ).first()

    claimed_redeemed_count = None
    if offer.usage_type != USAGE_TYPES["UNLIMITED"]:
        claimed_redeemed_count = _count_claimed_and_redeemed(offer.id)

    return evaluate_claim_rules(
        offer=offer,
        usage=usage,
        has_active_coupon=bool(existing_coupon),
        claimed_redeemed_count=claimed_redeemed_count,
        now=now
    )


def record_coupon_claim(
    consumer_id: str,
    offer_id: str,
    *,
    commit: bool = True
) -> UserOfferUsage:
    """
    Record that a user has claimed a coupon for an offer.

    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer

    Returns:
        UserOfferUsage: Updated usage record
    """
    usage = get_or_create_user_usage(
        consumer_id, offer_id, create_if_missing=True, commit=commit)
    if not usage:
        raise ValueError("Unable to create usage record")
    usage.record_claim(commit=commit)
    return usage


def record_coupon_redemption(
    consumer_id: str,
    offer_id: str,
    savings_amount: Optional[int] = None,
    *,
    commit: bool = True
) -> UserOfferUsage:
    """
    Record that a user has redeemed a coupon for an offer.

    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer
        savings_amount: Amount saved in cents (optional)

    Returns:
        UserOfferUsage: Updated usage record
    """
    usage = get_or_create_user_usage(
        consumer_id, offer_id, create_if_missing=True, commit=commit)
    if not usage:
        raise ValueError("Unable to create usage record")
    usage.record_redemption(savings_amount, commit=commit)
    return usage


def get_user_usage_stats(consumer_id: str, offer_id: Optional[str] = None) -> dict:
    """
    Get usage statistics for a user.

    Args:
        consumer_id: ID of the consumer
        offer_id: Optional specific offer ID

    Returns:
        dict: Usage statistics
    """
    query = db.session.query(UserOfferUsage).filter(
        UserOfferUsage.consumer_id == consumer_id
    )

    if offer_id:
        query = query.filter(UserOfferUsage.offer_id == offer_id)
        usage = query.first()
        if not usage:
            return {
                "usage_count": 0,
                "total_savings": 0,
                "total_redemptions": 0,
                "first_claimed_at": None,
                "last_claimed_at": None,
                "last_redemption_at": None,
                "average_days_between_usage": None
            }

        return {
            "usage_count": usage.usage_count,
            "total_savings": usage.total_savings,
            "total_redemptions": usage.total_redemptions,
            "first_claimed_at": usage.first_claimed_at.isoformat() if usage.first_claimed_at else None,
            "last_claimed_at": usage.last_claimed_at.isoformat() if usage.last_claimed_at else None,
            "last_redemption_at": usage.last_redemption_at.isoformat() if usage.last_redemption_at else None,
            "average_days_between_usage": usage.average_days_between_usage
        }
    else:
        # Return aggregate stats for all offers
        usages = query.all()
        total_savings = sum(u.total_savings for u in usages)
        total_claims = sum(u.usage_count for u in usages)
        total_redemptions = sum(u.total_redemptions for u in usages)
        unique_offers_claimed = len(usages)

        return {
            "total_savings": total_savings,
            "total_claims": total_claims,
            "total_redemptions": total_redemptions,
            "unique_offers_claimed": unique_offers_claimed,
            "average_savings_per_redemption": total_savings / total_redemptions if total_redemptions > 0 else 0
        }


def get_next_available_claim_time(consumer_id: str, offer_id: str) -> Optional[datetime]:
    """
    Get the next time a user can claim a coupon for an offer.

    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer

    Returns:
        Optional[datetime]: Next available claim time or None if can claim now
    """
    usage = db.session.query(UserOfferUsage).filter(
        UserOfferUsage.consumer_id == consumer_id,
        UserOfferUsage.offer_id == offer_id
    ).first()

    if not usage:
        return None

    return usage.next_available_claim


def calculate_tiered_discount(offer: Offer, usage_count: int) -> dict:
    """
    Calculate tiered discount based on usage count.

    Args:
        offer: The offer with tier progression
        usage_count: Current usage count for the user

    Returns:
        dict: Discount information for current tier
    """
    if not offer.tier_progression or offer.usage_type != USAGE_TYPES["TIERED"]:
        return {
            "discount_type": offer.discount_type,
            "discount_value": offer.discount_value,
            "tier": 1,
            "tier_name": "Standard"
        }

    # Example tier progression structure:
    # {
    #   "tiers": [
    #     {"min_usage": 0, "discount_multiplier": 1.0, "name": "Bronze"},
    #     {"min_usage": 3, "discount_multiplier": 1.2, "name": "Silver"},
    #     {"min_usage": 10, "discount_multiplier": 1.5, "name": "Gold"}
    #   ]
    # }

    tiers = offer.tier_progression.get("tiers", [])
    current_tier = {"min_usage": 0,
                    "discount_multiplier": 1.0, "name": "Standard"}

    for tier in sorted(tiers, key=lambda x: x["min_usage"], reverse=True):
        if usage_count >= tier["min_usage"]:
            current_tier = tier
            break

    # Calculate adjusted discount
    adjusted_value = int(offer.discount_value *
                         current_tier["discount_multiplier"])

    return {
        "discount_type": offer.discount_type,
        "discount_value": adjusted_value,
        "base_discount_value": offer.discount_value,
        "tier": current_tier["min_usage"] + 1,
        "tier_name": current_tier["name"],
        "tier_multiplier": current_tier["discount_multiplier"]
    }
