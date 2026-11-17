"""Student site: public offer pages, real profile figures and the partners list."""
from __future__ import annotations

import pytest

from tests.support import PASSWORD, access_token_from, bearer

pytestmark = pytest.mark.integration


def make_student(email):
    from app.models import Consumer
    student = Consumer(first_name="Achieng", last_name="Test", email=email, password=PASSWORD)
    student.save()
    return student


def login(client, student):
    response = client.post("/api/v1/auth/user/login", json={"email": student.email, "password": PASSWORD})
    assert response.status_code == 200
    client.delete_cookie("access_token")
    return bearer(access_token_from(response))



def test_guests_can_read_an_offer(client, db_session):
    from tests.support import make_merchant, make_offer

    offer = make_offer(make_merchant("shop@example.com", approved=True), "guest-readable")
    client.delete_cookie("access_token")

    response = client.get(f"/api/v1/offer/{offer.id}")

    assert response.status_code == 200
    assert response.get_json()["data"]["title"] == "Offer guest-readable"
