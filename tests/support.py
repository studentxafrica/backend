"""Shared helpers for API tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

PASSWORD = "Correct-Horse-Battery-1"


def access_token_from(response) -> str:
    """Pull the access token out of a login response's Set-Cookie header."""
    for header in response.headers.getlist("Set-Cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        if "access_token" in cookie:
            return cookie["access_token"].value
    raise AssertionError("response did not set an access token")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_merchant(email: str, approved: bool):
    from app.models import Merchant

    merchant = Merchant(name=email.split("@")[0], email=email, password=PASSWORD)
    if approved:
        merchant.approved_on = datetime.now(timezone.utc)
    merchant.save()
    return merchant


def make_offer(merchant, slug: str):
    from app.models.offer import Offer

    now = datetime.now(timezone.utc)
    offer = Offer(
        merchant_id=merchant.id,
        title=f"Offer {slug}",
        description="10% off",
        slug=slug,
        cover_image="https://example.com/cover.png",
        discount_type="percentage",
        discount_value=10,
        currency="KES",
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=30),
        # The model requires: start < highlighted < featured < end.
        featured_until=now + timedelta(days=14),
        highlighted_until=now + timedelta(days=7),
    )
    offer.save()
    return offer
