"""
Helper functions for flexible usage system validation and management.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from app.models.coupon import Coupon
from app.models.user_offer_usage import UserOfferUsage
from app.models.offer import Offer, USAGE_TYPES
from app.models.consumer import Consumer
from app import db


def get_or_create_user_usage(consumer_id: str, offer_id: str) -> UserOfferUsage:
    """
    Get existing user usage record or create a new one.
    
    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer
        
    Returns:
        UserOfferUsage: The usage record
    """
    usage = db.session.query(UserOfferUsage).filter(
        UserOfferUsage.consumer_id == consumer_id,
        UserOfferUsage.offer_id == offer_id
    ).first()
    
    if not usage:
        usage = UserOfferUsage(
            consumer_id=consumer_id,
            offer_id=offer_id,
            usage_count=0,
            total_savings=0,
            total_redemptions=0
        )
        usage.save()
    
    return usage


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
    
    # Check if offer is active and not expired
    now = datetime.now(timezone.utc)
    if offer.status != 'active':
        return False, "Offer is not active"
    
    # Ensure offer.end_date is timezone-aware for comparison
    end_date = offer.end_date
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    if end_date <= now:
        return False, "Offer has expired"
    
    usage = get_or_create_user_usage(consumer_id, offer_id)
    
    # Check usage type rules
    if offer.usage_type == USAGE_TYPES["SINGLE_USE"]:
        if usage.usage_count > 0:
            return False, "You have already claimed a coupon for this offer"
        return True, ""
    
    elif offer.usage_type == USAGE_TYPES["MULTI_USE"]:
        # Check usage limit
        if usage.usage_count >= offer.max_claims_per_user:
            return False, f"Maximum claims per user ({offer.max_claims_per_user}) reached"
        
        # Check cooldown period
        if usage.last_claimed_at and offer.cooldown_period_hours:
            time_since_last = now - usage.last_claimed_at
            cooldown_seconds = offer.cooldown_period_hours * 3600
            if time_since_last.total_seconds() < cooldown_seconds:
                remaining_hours = (cooldown_seconds - time_since_last.total_seconds()) / 3600
                return False, f"Cooldown period active. Try again in {remaining_hours:.1f} hours"
        
        return True, ""
    
    elif offer.usage_type == USAGE_TYPES["UNLIMITED"]:
        # Check cooldown period only
        if usage.last_claimed_at and offer.cooldown_period_hours:
            time_since_last = now - usage.last_claimed_at
            cooldown_seconds = offer.cooldown_period_hours * 3600
            if time_since_last.total_seconds() < cooldown_seconds:
                remaining_hours = (cooldown_seconds - time_since_last.total_seconds()) / 3600
                return False, f"Cooldown period active. Try again in {remaining_hours:.1f} hours"
        #  Check if user has an unredeemed coupon for this offer
        from app.models.coupon import Coupon
        existing_coupon = db.session.query(Coupon).filter(
            Coupon.offer_id == offer.id,
            Coupon.consumer_id == consumer_id,
            Coupon.status == 'active'
        ).first()
        if existing_coupon:
            return False, "You have an unredeemed coupon for this offer"
        return True, ""
    
    elif offer.usage_type == USAGE_TYPES["TIERED"]:
        # For now, treat tiered as multi-use with progression
        # TODO: Implement tier-specific logic based on tier_progression JSON
        if usage.usage_count >= offer.max_claims_per_user:
            return False, f"Maximum claims per user ({offer.max_claims_per_user}) reached"
        
        return True, ""
    
    return False, "Unknown usage type"


def record_coupon_claim(consumer_id: str, offer_id: str) -> UserOfferUsage:
    """
    Record that a user has claimed a coupon for an offer.
    
    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer
        
    Returns:
        UserOfferUsage: Updated usage record
    """
    usage = get_or_create_user_usage(consumer_id, offer_id)
    usage.record_claim()
    return usage


def record_coupon_redemption(consumer_id: str, offer_id: str, savings_amount: Optional[int] = None) -> UserOfferUsage:
    """
    Record that a user has redeemed a coupon for an offer.
    
    Args:
        consumer_id: ID of the consumer
        offer_id: ID of the offer
        savings_amount: Amount saved in cents (optional)
        
    Returns:
        UserOfferUsage: Updated usage record
    """
    usage = get_or_create_user_usage(consumer_id, offer_id)
    usage.record_redemption(savings_amount)
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
    current_tier = {"min_usage": 0, "discount_multiplier": 1.0, "name": "Standard"}
    
    for tier in sorted(tiers, key=lambda x: x["min_usage"], reverse=True):
        if usage_count >= tier["min_usage"]:
            current_tier = tier
            break
    
    # Calculate adjusted discount
    adjusted_value = int(offer.discount_value * current_tier["discount_multiplier"])
    
    return {
        "discount_type": offer.discount_type,
        "discount_value": adjusted_value,
        "base_discount_value": offer.discount_value,
        "tier": current_tier["min_usage"] + 1,
        "tier_name": current_tier["name"],
        "tier_multiplier": current_tier["discount_multiplier"]
    }