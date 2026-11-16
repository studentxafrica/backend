import pytest

from tests.support import PASSWORD, access_token_from, bearer

pytestmark = pytest.mark.integration

NEW_PASSWORD = "Another-Strong-Pass-2"


def reset_with(client, token, password=NEW_PASSWORD):
    return client.post(
        f"/api/v1/auth/user/confirm-reset-password?token={token}",
        json={"password": password},
    )


def reset_token_for(app, user):
    from app.email import generate_password_reset_token

    with app.test_request_context():
        return generate_password_reset_token(user)


def test_reset_token_changes_the_password(app, client, consumer):
    response = reset_with(client, reset_token_for(app, consumer))

    assert response.status_code == 200
    login = client.post(
        "/api/v1/auth/user/login",
        json={"email": consumer.email, "password": NEW_PASSWORD},
    )
    assert login.status_code == 200


def test_reset_token_works_only_once(app, client, consumer):
    token = reset_token_for(app, consumer)

    assert reset_with(client, token).status_code == 200
    second = reset_with(client, token, password="Attacker-Chosen-Pass-3")

    assert second.status_code == 400
    login = client.post(
        "/api/v1/auth/user/login",
        json={"email": consumer.email, "password": NEW_PASSWORD},
    )
    assert login.status_code == 200


def test_reset_token_stops_working_after_password_changes(app, client, consumer):
    token = reset_token_for(app, consumer)
    consumer.password = "Changed-Elsewhere-4"
    consumer.save()

    assert reset_with(client, token).status_code == 400


def test_confirmation_token_is_rejected_by_password_reset(app, client, consumer):
    from app.email import generate_confirmation_token

    with app.test_request_context():
        confirmation_token = generate_confirmation_token(consumer.email)

    response = reset_with(client, confirmation_token)

    assert response.status_code == 400
    login = client.post(
        "/api/v1/auth/user/login",
        json={"email": consumer.email, "password": PASSWORD},
    )
    assert login.status_code == 200


def test_reset_token_is_rejected_by_email_confirmation(app, client, consumer):
    token = reset_token_for(app, consumer)

    response = client.get(f"/api/v1/auth/user/merchant/confirm-email?token={token}")

    assert response.status_code == 400


def test_password_reset_signs_out_existing_sessions(app, client, consumer, consumer_token):
    assert client.get("/api/v1/user/me", headers=bearer(consumer_token)).status_code == 200

    assert reset_with(client, reset_token_for(app, consumer)).status_code == 200

    assert client.get("/api/v1/user/me", headers=bearer(consumer_token)).status_code == 401
    new_login = client.post(
        "/api/v1/auth/user/login",
        json={"email": consumer.email, "password": NEW_PASSWORD},
    )
    new_token = access_token_from(new_login)
    assert client.get("/api/v1/user/me", headers=bearer(new_token)).status_code == 200


def test_token_without_password_binding_is_rejected(app, client, consumer):
    from flask_jwt_extended import create_access_token

    with app.test_request_context():
        unbound = create_access_token(identity=consumer.id)

    assert client.get("/api/v1/user/me", headers=bearer(unbound)).status_code == 401


def test_token_signed_with_another_key_is_rejected(app, client, consumer):
    import jwt as pyjwt

    from app.security import password_fingerprint

    with app.test_request_context():
        forged = pyjwt.encode(
            {"sub": consumer.id, "type": "access", "fresh": False,
             "pwd": password_fingerprint(consumer)},
            "some-other-signing-key-that-is-long-enough",
            algorithm="HS256",
        )

    assert client.get("/api/v1/user/me", headers=bearer(forged)).status_code in (401, 422)
