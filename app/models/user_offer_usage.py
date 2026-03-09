from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base_model import BaseModel
from app import db


class UserOfferUsage(BaseModel, db.Model):
    """
    UserOfferUsage model for tracking user interaction with offers.
    Enables flexible discount systems with multiple usage patterns.
    """
    __tablename__ = 'user_offer_usage'

    # Foreign Keys
    consumer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('consumers.id'), nullable=False, index=True)
    offer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('offers.id'), nullable=False, index=True)

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False)
    last_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    first_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    total_savings: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False)  # in cents

    # Usage statistics
    total_redemptions: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False)
    average_days_between_usage: Mapped[int | None] = mapped_column(
        Integer, nullable=True)
    last_redemption_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)

    # Relationships
    consumer = relationship('Consumer', backref='offer_usage_history')
    offer = relationship('Offer', back_populates='user_usage_stats')

    def __str__(self):
        return f"Usage: {self.consumer.first_name} - {self.offer.title} ({self.usage_count}x)"

    @property
    def can_claim_more(self):
        """Check if user can claim more coupons based on offer settings"""
        if self.offer.usage_type == 'single_use':
            return self.usage_count == 0
        elif self.offer.usage_type == 'multi_use':
            if self.usage_count >= self.offer.max_claims_per_user:
                return False
            # Check cooldown period
            if self.last_claimed_at is not None and self.offer.cooldown_period_hours:
                time_since_last_claim = datetime.now(
                    timezone.utc) - self.last_claimed_at
                cooldown_hours = self.offer.cooldown_period_hours
                return time_since_last_claim.total_seconds() >= (cooldown_hours * 3600)
            return True
        elif self.offer.usage_type == 'unlimited':
            # Check cooldown period only
            if self.last_claimed_at is not None and self.offer.cooldown_period_hours:
                time_since_last_claim = datetime.now(
                    timezone.utc) - self.last_claimed_at
                cooldown_hours = self.offer.cooldown_period_hours
                return time_since_last_claim.total_seconds() >= (cooldown_hours * 3600)
            return True
        return False

    @property
    def next_available_claim(self):
        """Calculate when user can next claim this offer"""
        if not self.offer.cooldown_period_hours or self.last_claimed_at is None:
            return None

        cooldown_end = self.last_claimed_at.timestamp(
        ) + (self.offer.cooldown_period_hours * 3600)
        return datetime.fromtimestamp(cooldown_end, tz=timezone.utc)

    def record_claim(self, commit: bool = True):
        """Record a new claim"""
        now = datetime.now(timezone.utc)

        if self.usage_count == 0:
            self.first_claimed_at = now

        self.usage_count += 1
        self.last_claimed_at = now
        self.updated_at = now
        if commit:
            self.save()
        else:
            db.session.flush()

    def record_redemption(self, savings_amount=None, commit: bool = True):
        """Record a redemption and optional savings amount"""
        self.total_redemptions += 1
        self.last_redemption_at = datetime.now(timezone.utc)

        if savings_amount:
            self.total_savings += savings_amount

        # Calculate average days between usage
        last_redemption_at = self.last_redemption_at
        first_claimed_at = self.first_claimed_at
        if last_redemption_at is not None and first_claimed_at is not None and self.total_redemptions > 1:
            days_since_first = (last_redemption_at - first_claimed_at).days
            self.average_days_between_usage = days_since_first // self.total_redemptions

        self.updated_at = datetime.now(timezone.utc)
        if commit:
            self.save()
        else:
            db.session.flush()
