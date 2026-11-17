"""Promotional email consent, and keeping the Brevo list in step with it."""
from __future__ import annotations

import pytest

from tests.support import PASSWORD, access_token_from, bearer

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def no_mail(monkeypatch):
    monkeypatch.setattr("app.email.send_email", lambda **kw: None)


@pytest.fixture
def background_syncs(monkeypatch):
    calls = []
    monkeypatch.setattr("app.brevo.sync_member_soon", lambda *a, **kw: calls.append((a, kw)))
    return calls


@pytest.fixture
def brevo(app, monkeypatch):
    """Point the sync at a stand-in Brevo that records every call."""
    app.config.update(BREVO_API_KEY="test-key", BREVO_LIST_ID="7")
    state = {"calls": [], "list": []}

    def fake_call(method, path, json=None, params=None, ok=None):
        state["calls"].append((method, path, json))
        if method == "GET":
            return {"contacts": state["list"], "count": len(state["list"])}
        return {}

    monkeypatch.setattr("app.brevo._call", fake_call)
    yield state
    app.config.update(BREVO_API_KEY=None, BREVO_LIST_ID=None)


def register(client, email, **extra):
    return client.post("/api/v1/auth/user/consumer/register", json={
        "first_name": "Achieng", "last_name": "O", "email": email, "password": PASSWORD, **extra})


def make_member(email, consent):
    from app.models import Consumer
    member = Consumer(first_name="Baraka", last_name="M", email=email, password=PASSWORD)
    if consent:
        member.set_marketing_consent(True, "existing_member")
    member.save()
    return member


def login(client, email):
    response = client.post("/api/v1/auth/user/login", json={"email": email, "password": PASSWORD})
    client.delete_cookie("access_token")
    return bearer(access_token_from(response))


# Consent ----------------------------------------------------------------------

def test_new_members_are_opted_out_unless_they_tick_the_box(client, db_session, background_syncs):
    from app.models import Consumer

    assert register(client, "quiet@example.com").status_code == 201
    assert register(client, "keen@example.com", marketing_consent=True).status_code == 201

    quiet = db_session.query(Consumer).filter_by(email="quiet@example.com").one()
    keen = db_session.query(Consumer).filter_by(email="keen@example.com").one()
    assert quiet.marketing_consent is False
    assert (keen.marketing_consent, keen.marketing_consent_source) == (True, "signup")
    # Only the member who agreed is sent to Brevo
    assert [a[0] for a, _ in background_syncs] == [keen.id]


def test_members_can_turn_promotional_email_on_and_off(client, db_session, background_syncs):
    make_member("toggle@example.com", consent=False)
    headers = login(client, "toggle@example.com")

    assert client.get("/api/v1/user/me", headers=headers).get_json()["data"]["marketingEmails"] is False

    on = client.put("/api/v1/user/me/marketing-emails", json={"subscribed": True}, headers=headers)
    assert on.status_code == 200 and on.get_json()["data"]["marketingEmails"] is True
    assert background_syncs[-1][1] == {"resubscribe": True}

    off = client.put("/api/v1/user/me/marketing-emails", json={"subscribed": False}, headers=headers)
    assert off.get_json()["data"]["marketingEmails"] is False

    bad = client.put("/api/v1/user/me/marketing-emails", json={"subscribed": "yes"}, headers=headers)
    assert bad.status_code == 400


# Brevo webhook -------------------------------------------------------------------

def test_unsubscribing_in_brevo_opts_the_member_out(app, client, db_session):
    member = make_member("leaving@example.com", consent=True)
    app.config["BREVO_WEBHOOK_TOKEN"] = "hook-secret"
    try:
        url = "/api/v1/integrations/brevo/webhook"
        event = {"event": "unsubscribe", "email": "leaving@example.com"}
        assert client.post(url, json=event).status_code == 401
        assert client.post(url, json=event, headers={"Authorization": "Bearer wrong"}).status_code == 401

        ignored = client.post(url, json={"event": "opened", "email": "leaving@example.com"},
                              headers={"Authorization": "Bearer hook-secret"})
        assert ignored.get_json()["updated"] == 0

        done = client.post(url, json=event, headers={"Authorization": "Bearer hook-secret"})
        assert done.get_json()["updated"] == 1
        db_session.refresh(member)
        assert (member.marketing_consent, member.marketing_consent_source) == (False, "unsubscribe_link")
    finally:
        app.config["BREVO_WEBHOOK_TOKEN"] = None


# Sync ------------------------------------------------------------------------------

def test_full_sync_sends_only_consenting_members(app, db_session, brevo):
    from app import db
    from app.brevo import full_sync
    from app.models import Consumer

    keen = make_member("keen@example.com", consent=True)
    unsubscribed = make_member("unsub@example.com", consent=True)
    make_member("never@example.com", consent=False)
    withdrew = make_member("withdrew@example.com", consent=False)
    brevo["list"] = [
        {"email": "unsub@example.com", "emailBlacklisted": True},
        {"email": "withdrew@example.com", "emailBlacklisted": False},
        {"email": "gone@example.com", "emailBlacklisted": False},
    ]

    result = full_sync(db.session, Consumer)

    db_session.refresh(unsubscribed)
    assert unsubscribed.marketing_consent is False
    imported = [c for c in brevo["calls"] if c[1] == "/contacts/import"]
    assert [row["email"] for row in imported[0][2]["jsonBody"]] == [keen.email]
    assert imported[0][2]["jsonBody"][0]["attributes"]["EXT_ID"] == keen.id
    removed = [c for c in brevo["calls"] if c[1].endswith("/contacts/remove")]
    assert sorted(removed[0][2]["emails"]) == sorted(["unsub@example.com", withdrew.email, "gone@example.com"])
    assert "never@example.com" not in repr(brevo["calls"])
    assert result == {"opted_out_from_brevo": 1, "on_list": 1, "removed": 3}


def test_dry_run_changes_nothing(app, db_session, brevo):
    from app import db
    from app.brevo import full_sync
    from app.models import Consumer

    member = make_member("unsub@example.com", consent=True)
    brevo["list"] = [{"email": "unsub@example.com", "emailBlacklisted": True}]

    result = full_sync(db.session, Consumer, dry_run=True)

    db_session.refresh(member)
    assert member.marketing_consent is True
    assert [c[0] for c in brevo["calls"]] == ["GET"]
    assert result["opted_out_from_brevo"] == 1


def test_one_member_sync_follows_consent_and_email_changes(app, db_session, brevo):
    from app.brevo import sync_member

    member = make_member("old@example.com", consent=True)
    member.email = "new@example.com"
    sync_member(member, previous_email="old@example.com", resubscribe=True)
    put, post = brevo["calls"]
    assert put[0] == "PUT" and put[1] == "/contacts/old%40example.com" and put[2] == {"attributes": {"EMAIL": "new@example.com"}}
    assert post[1] == "/contacts" and post[2]["listIds"] == [7] and post[2]["emailBlacklisted"] is False

    member.set_marketing_consent(False, "profile")
    sync_member(member)
    assert brevo["calls"][-1][1] == "/contacts/lists/7/contacts/remove"
    assert brevo["calls"][-1][2] == {"emails": ["new@example.com"]}


def test_sync_does_nothing_without_brevo_settings(app, db_session, monkeypatch):
    from app.brevo import sync_member

    monkeypatch.setattr("app.brevo._call", lambda *a, **kw: pytest.fail("Brevo should not be called"))
    sync_member(make_member("x@example.com", consent=True))
