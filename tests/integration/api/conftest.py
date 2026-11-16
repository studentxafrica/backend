from __future__ import annotations

import pytest

from tests.support import PASSWORD, access_token_from


@pytest.fixture
def consumer(db_session):
    from app.models import Consumer

    user = Consumer(
        first_name="Amina",
        last_name="Otieno",
        email="amina@example.com",
        password=PASSWORD,
    )
    user.save()
    return user


@pytest.fixture
def admin(db_session):
    from app.models import Administrator

    user = Administrator(
        username="ops-admin",
        email="ops-admin@example.com",
        first_name="Ops",
        last_name="Admin",
        password=PASSWORD,
    )
    user.save()
    return user


@pytest.fixture
def consumer_token(client, consumer):
    response = client.post(
        "/api/v1/auth/user/login",
        json={"email": consumer.email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return access_token_from(response)


@pytest.fixture
def admin_token(client, admin):
    response = client.post(
        "/api/v1/auth/admin/login",
        json={"username": admin.username, "password": PASSWORD},
    )
    assert response.status_code == 200
    return access_token_from(response)
