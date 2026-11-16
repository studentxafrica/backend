import pytest

from tests.support import bearer, make_merchant, make_offer

pytestmark = pytest.mark.integration

REGISTER_URL = "/api/v1/admin/merchants/register"


def test_merchant_registration_requires_login(client, db_session):
    from app.models import Merchant

    response = client.post(REGISTER_URL, json={"email": "new@example.com"})

    assert response.status_code == 401
    assert db_session.query(Merchant).count() == 0


def test_merchant_registration_rejects_non_admins(client, consumer_token, db_session):
    from app.models import Merchant

    response = client.post(
        REGISTER_URL, json={"email": "new@example.com"}, headers=bearer(consumer_token)
    )

    assert response.status_code in (401, 403)
    assert db_session.query(Merchant).count() == 0


def test_admin_can_register_merchant(client, admin_token, db_session):
    from app.models import Merchant

    response = client.post(
        REGISTER_URL, json={"email": "new@example.com"}, headers=bearer(admin_token)
    )

    assert response.status_code == 201
    assert db_session.query(Merchant).filter_by(email="new@example.com").count() == 1


@pytest.fixture
def offers(db_session):
    approved = make_offer(make_merchant("approved@example.com", approved=True), "approved-offer")
    pending = make_offer(make_merchant("pending@example.com", approved=False), "pending-offer")
    return approved, pending


def offer_ids(payload):
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    return {item["id"] for item in items}


@pytest.mark.parametrize("path", [
    "/api/v1/offer/featured",
    "/api/v1/offer/latest",
    "/api/v1/offer/highlighted",
    "/api/v1/offer/recommended",
    "/api/v1/offer/",
])
def test_offer_lists_hide_unapproved_merchants(client, offers, path):
    approved, pending = offers

    response = client.get(path)

    assert response.status_code == 200
    ids = offer_ids(response.get_json())
    assert approved.id in ids
    assert pending.id not in ids


def test_offer_from_unapproved_merchant_cannot_be_opened(client, offers, consumer_token):
    approved, pending = offers

    assert client.get(f"/api/v1/offer/{approved.id}", headers=bearer(consumer_token)).status_code == 200
    assert client.get(f"/api/v1/offer/{pending.id}", headers=bearer(consumer_token)).status_code == 404


def test_offer_from_unapproved_merchant_cannot_be_claimed(client, offers, consumer_token):
    _, pending = offers

    response = client.post(
        f"/api/v1/offer/{pending.id}/coupons/create", headers=bearer(consumer_token)
    )

    # Unverified students are refused first; either way nothing is claimed.
    assert response.status_code in (403, 404)


def test_similar_offers_hide_unapproved_merchants(client, offers):
    approved, pending = offers

    response = client.get(f"/api/v1/offer/{approved.id}/similar")

    assert response.status_code == 200
    assert pending.id not in offer_ids(response.get_json())
    assert client.get(f"/api/v1/offer/{pending.id}/similar").status_code == 404
