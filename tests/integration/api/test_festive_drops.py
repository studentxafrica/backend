"""Festive Drops: joining, random picks, results, crews and live passes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.support import PASSWORD, access_token_from, bearer

pytestmark = pytest.mark.integration

SLUG = "studentxmas"


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def sent_mail(monkeypatch):
    """Capture emails instead of sending them."""
    sent = []
    monkeypatch.setattr("app.email.send_email", lambda **kw: sent.append(kw))
    return sent


def make_student(email, verified=True, phone="+254712345678", first="Achieng"):
    from app.models import Consumer
    from app.models.consumer import VerificationRequestStatus

    student = Consumer(first_name=first, last_name="Test", email=email, password=PASSWORD, phone=phone)
    if verified:
        student.verified_at = utcnow() - timedelta(days=1)
        student.verification_status = VerificationRequestStatus.APPROVED
    student.save()
    return student


def login(client, student):
    """Sign in and return headers for that student. The cookie the login sets is
    cleared, because the API reads the cookie before the header."""
    response = client.post("/api/v1/auth/user/login", json={"email": student.email, "password": PASSWORD})
    assert response.status_code == 200
    client.delete_cookie("access_token")
    return bearer(access_token_from(response))


def make_campaign(drops):
    """drops: list of (hours from now, kind, quantity, crew_size)."""
    from app import db
    from app.models.campaign import Campaign, Drop

    now = utcnow()
    campaign = Campaign(slug=SLUG, name="StudentXmas Festive Drops", starts_at=now - timedelta(days=2),
                        ends_at=now + timedelta(days=30), terms_version="t1", max_picks_per_member=1)
    made = []
    for i, (hours, kind, quantity, crew) in enumerate(drops):
        made.append(Drop(campaign_id=campaign.id, title=f"Drop {i}", brand="Safaricom", kind=kind,
                         quantity=quantity, crew_size=crew, pick_at=now + timedelta(hours=hours),
                         use_within_days=10))
    db.session.commit()
    return campaign, made


def join(client, headers, **body):
    return client.post(f"/api/v1/drops/campaigns/{SLUG}/join", json={"acceptTerms": True, **body}, headers=headers)


def backdate_membership(campaign, student, hours):
    from app import db
    from app.models.campaign import CampaignMember
    member = db.session.query(CampaignMember).filter_by(campaign_id=campaign.id, consumer_id=student.id).one()
    member.joined_at = utcnow() - timedelta(hours=hours)
    db.session.commit()


# Registration ---------------------------------------------------------------

def test_registration_saves_phone_and_date_of_birth(client, db_session):
    from app.models import Consumer

    response = client.post("/api/v1/auth/user/consumer/register", json={
        "first_name": "Wanjiru", "last_name": "K", "email": "w@example.com", "password": PASSWORD,
        "phone": "0712 345 678", "date_of_birth": "2004-05-17"})

    assert response.status_code == 201
    student = db_session.query(Consumer).filter_by(email="w@example.com").one()
    assert student.phone == "+254712345678"
    assert student.date_of_birth.date().isoformat() == "2004-05-17"


def test_registration_refuses_a_non_kenyan_phone(client, db_session):
    response = client.post("/api/v1/auth/user/consumer/register", json={
        "first_name": "X", "last_name": "Y", "email": "x@example.com", "password": PASSWORD, "phone": "12345"})

    assert response.status_code == 400


# Campaign page ---------------------------------------------------------------

def test_campaign_page_lists_next_drop_first_and_ended_drops_separately(client, db_session):
    from app.drops.service import run_pick

    campaign, drops = make_campaign([(48, "airtime", 2, None), (-2, "airtime", 2, None),
                                     (24, "voucher", 1, None), (-26, "voucher", 1, None)])
    run_pick(drops[1].id, "test")
    run_pick(drops[3].id, "test")

    data = client.get(f"/api/v1/drops/campaigns/{SLUG}").get_json()["data"]

    assert [d["title"] for d in data["upcoming"]] == ["Drop 2", "Drop 0"]
    assert data["upcoming"][0]["isNext"] is True and data["nextDrop"]["title"] == "Drop 2"
    assert [d["title"] for d in data["ended"]] == ["Drop 1", "Drop 3"]
    assert all(d["status"] == "ended" for d in data["ended"])
    assert data["member"]["state"] == "visitor"


# Joining ---------------------------------------------------------------

def test_any_student_can_join_but_only_verified_members_are_picked(client, db_session):
    from app.drops.service import run_pick

    campaign, drops = make_campaign([(-1, "airtime", 2, None)])
    unverified = make_student("u@example.com", verified=False)
    verified = make_student("v@example.com")
    for s in (unverified, verified):
        response = join(client, login(client, s))
        assert response.status_code == 201
        backdate_membership(campaign, s, 5)
    assert response.get_json()["data"]["member"]["verification"] == "verified"

    run = run_pick(drops[0].id, "test")

    assert run.eligible_count == 1 and run.picked_count == 1
    view = client.get(f"/api/v1/drops/campaigns/{SLUG}", headers=login(client, unverified)).get_json()["data"]
    assert view["member"]["state"] == "joined" and view["member"]["verification"] == "unverified"
    assert view["ended"][0]["result"] == "not_verified"


def test_joining_needs_a_phone_and_can_supply_one(client, db_session):
    make_campaign([(24, "airtime", 2, None)])
    student = make_student("p@example.com", phone=None)
    headers = login(client, student)

    assert join(client, headers).status_code == 400
    response = join(client, headers, phone="0798 765 432")
    assert response.status_code == 201
    assert response.get_json()["data"]["member"]["state"] == "joined"
    assert join(client, headers).status_code == 200


def test_joining_needs_agreement_to_the_terms(client, db_session):
    make_campaign([(24, "airtime", 2, None)])
    student = make_student("t@example.com")

    response = client.post(f"/api/v1/drops/campaigns/{SLUG}/join", json={}, headers=login(client, student))

    assert response.status_code == 400


# Picking ---------------------------------------------------------------

def test_pick_chooses_quantity_from_members_and_never_picks_anyone_twice(client, db_session, sent_mail):
    from app.drops.service import run_pick
    from app.models.campaign import DropPick

    campaign, drops = make_campaign([(-3, "airtime", 2, None), (-2, "airtime", 2, None), (-1, "airtime", 2, None)])
    students = [make_student(f"s{i}@example.com") for i in range(5)]
    for s in students:
        assert join(client, login(client, s)).status_code == 201
        backdate_membership(campaign, s, 10)

    runs = [run_pick(d.id, "test") for d in drops]

    assert [r.picked_count for r in runs] == [2, 2, 1]
    assert [r.eligible_count for r in runs] == [5, 3, 1]
    assert runs[2].shortfall == 1
    picked = [p.consumer_id for p in db_session.query(DropPick).all()]
    assert len(picked) == len(set(picked)) == 5
    assert len(sent_mail) == 5


def test_pick_is_idempotent_and_waits_for_its_time(client, db_session):
    from app.drops.service import DropError, run_pick

    campaign, drops = make_campaign([(-1, "airtime", 1, None), (5, "airtime", 1, None)])
    first = run_pick(drops[0].id, "test")
    again = run_pick(drops[0].id, "test")

    assert first.id == again.id
    with pytest.raises(DropError):
        run_pick(drops[1].id, "test")


def test_members_who_joined_after_the_pick_time_are_not_in_it(client, db_session):
    from app.drops.service import run_pick

    campaign, drops = make_campaign([(-1, "airtime", 2, None)])
    student = make_student("late@example.com")
    join(client, login(client, student))  # joined now, after the pick time

    assert run_pick(drops[0].id, "test").eligible_count == 0


def test_results_tell_each_member_their_own_outcome_only(client, db_session):
    from app.drops.service import run_pick

    campaign, drops = make_campaign([(-1, "airtime", 1, None)])
    alice, brian = make_student("a@example.com", first="Alice"), make_student("b@example.com", first="Brian")
    for s in (alice, brian):
        join(client, login(client, s))
        backdate_membership(campaign, s, 5)
    run_pick(drops[0].id, "test")

    results = {}
    for s in (alice, brian):
        response = client.get(f"/api/v1/drops/campaigns/{SLUG}", headers=login(client, s))
        body = response.get_data(as_text=True)
        results[s.first_name] = response.get_json()["data"]["latestResult"]["result"]
        other = "Brian" if s is alice else "Alice"
        assert other not in body and "@example.com" not in body
    assert sorted(results.values()) == ["not_picked", "picked"]


def test_admin_pick_endpoint_needs_an_admin(client, db_session, consumer_token, admin_token):
    campaign, drops = make_campaign([(-1, "airtime", 1, None)])
    client.delete_cookie("access_token")

    assert client.post(f"/api/v1/drops/admin/drops/{drops[0].id}/pick", headers=bearer(consumer_token)).status_code in (401, 403)
    response = client.post(f"/api/v1/drops/admin/drops/{drops[0].id}/pick", headers=bearer(admin_token))
    assert response.status_code == 200
    assert response.get_json()["data"]["eligible"] == 0


# Crews and passes ---------------------------------------------------------------

def test_crew_pass_is_issued_once_every_friend_is_verified(client, db_session):
    from app.drops.service import run_pick
    from app.models.campaign import DropPick
    from app.models.consumer import VerificationRequestStatus

    campaign, drops = make_campaign([(-1, "crew", 1, 3)])
    winner = make_student("w@example.com")
    join(client, login(client, winner))
    backdate_membership(campaign, winner, 5)
    run_pick(drops[0].id, "test")
    pick = db_session.query(DropPick).one()
    winner_headers = login(client, winner)

    assert client.get(f"/api/v1/drops/picks/{pick.id}/pass", headers=winner_headers).status_code == 409

    friend1 = make_student("f1@example.com")
    friend2 = make_student("f2@example.com", verified=False)
    assert client.get(f"/api/v1/drops/crew/{pick.crew_code}").get_json()["data"]["spotsLeft"] == 2
    assert client.post(f"/api/v1/drops/crew/{pick.crew_code}/join", headers=login(client, friend1)).status_code == 201
    assert client.post(f"/api/v1/drops/crew/{pick.crew_code}/join", headers=login(client, friend2)).status_code == 201
    extra = make_student("f3@example.com")
    assert client.post(f"/api/v1/drops/crew/{pick.crew_code}/join", headers=login(client, extra)).status_code == 400
    assert client.get(f"/api/v1/drops/picks/{pick.id}/pass", headers=winner_headers).status_code == 409

    friend2.verified_at = utcnow()
    friend2.verification_status = VerificationRequestStatus.APPROVED
    friend2.save()
    assert client.get(f"/api/v1/drops/picks/{pick.id}/pass", headers=winner_headers).status_code == 200


def test_venue_checks_and_redeems_a_live_pass_once(client, db_session, admin_token):
    from app.drops.service import run_pick
    from app.models.campaign import DropPick

    campaign, drops = make_campaign([(-1, "voucher", 1, None)])
    student = make_student("v@example.com")
    join(client, login(client, student))
    backdate_membership(campaign, student, 5)
    run_pick(drops[0].id, "test")
    pick = db_session.query(DropPick).one()
    code = client.get(f"/api/v1/drops/picks/{pick.id}/pass", headers=login(client, student)).get_json()["data"]["code"]

    check = client.get(f"/api/v1/drops/passes/check?code={code}").get_json()["data"]
    assert check["valid"] is True and check["firstName"] == "Achieng"
    assert client.get("/api/v1/drops/passes/check?code=AAAAAA").get_json()["data"]["valid"] is False

    client.delete_cookie("access_token")
    assert client.post(f"/api/v1/drops/admin/drops/{drops[0].id}/venue-pin", json={"pin": "4821"},
                       headers=bearer(admin_token)).status_code == 200
    assert client.post("/api/v1/drops/passes/redeem", json={"code": code, "pin": "0000"}).status_code == 403
    assert client.post("/api/v1/drops/passes/redeem", json={"code": code, "pin": "4821"}).status_code == 200
    assert client.post("/api/v1/drops/passes/redeem", json={"code": code, "pin": "4821"}).status_code == 409


def test_pass_codes_change_every_30_seconds(db_session):
    from app.drops.service import pass_code, run_pick
    from app.models.campaign import DropPick

    campaign, drops = make_campaign([(-1, "voucher", 1, None)])
    student = make_student("c@example.com")
    from app.drops.service import join_campaign
    join_campaign(campaign, student, True)
    backdate_membership(campaign, student, 5)
    run_pick(drops[0].id, "test")
    pick = db_session.query(DropPick).one()
    t = datetime(2026, 11, 20, 9, 0, 0)

    assert pass_code(pick, t) == pass_code(pick, t + timedelta(seconds=29))
    assert pass_code(pick, t) != pass_code(pick, t + timedelta(seconds=30))


def test_seed_command_creates_the_twelve_studentxmas_drops_once(app, db_session):
    from app.models.campaign import Campaign

    runner = app.test_cli_runner()
    assert "Created StudentXmas with 12 drops" in runner.invoke(args=["drops", "seed-studentxmas"]).output
    assert "nothing changed" in runner.invoke(args=["drops", "seed-studentxmas"]).output
    campaign = db_session.query(Campaign).filter_by(slug="studentxmas").one()
    assert [d.quantity for d in campaign.drops] == [2, 2, 1, 2, 2, 1, 2, 2, 1, 1, 1, 1]
    assert campaign.drops[0].pick_at == datetime(2026, 11, 20, 9, 0)


def test_admin_overview_flags_drops_ready_to_pick_and_edits_a_drop(client, db_session, admin_token):
    campaign, drops = make_campaign([(-1, "voucher", 1, None), (24, "airtime", 2, None)])
    client.delete_cookie("access_token")
    headers = bearer(admin_token)

    data = client.get(f"/api/v1/drops/admin/campaigns/{SLUG}", headers=headers).get_json()["data"]
    assert [d["readyToPick"] for d in data["drops"]] == [True, False]
    assert data["drops"][0]["venuePinSet"] is False

    response = client.put(f"/api/v1/drops/admin/drops/{drops[0].id}", headers=headers,
                          json={"brand": "Java House", "title": "KSh 1,500 Java House voucher",
                                "coverImage": "https://example.com/coffee.jpg"})
    assert response.status_code == 200
    page = client.get(f"/api/v1/drops/campaigns/{SLUG}").get_json()["data"]
    assert page["upcoming"][0]["brand"] == "Java House"
    assert page["upcoming"][0]["coverImage"] == "https://example.com/coffee.jpg"
    assert client.put(f"/api/v1/drops/admin/drops/{drops[0].id}", headers=headers, json={"title": ""}).status_code == 400


def test_run_due_picks_drops_whose_time_has_passed(app, client, db_session):
    from app.models.campaign import DropPick

    campaign, drops = make_campaign([(-1, "airtime", 1, None), (24, "airtime", 1, None)])
    student = make_student("due@example.com")
    assert join(client, login(client, student)).status_code == 201
    backdate_membership(campaign, student, 10)

    result = app.test_cli_runner().invoke(args=["drops", "run-due"])
    assert "picked 1 of 1 eligible" in result.output
    assert [p.drop_id for p in db_session.query(DropPick).all()] == [drops[0].id]


# Winner email --------------------------------------------------------------

@pytest.mark.parametrize("kind,crew_size,expect,leave_out", [
    ("airtime", None, ["Sent directly to your phone number (0712 ••• 678)", "credited directly"], ["Present Your StudentX ID", "/crew/"]),
    ("voucher", None, ["Present Your StudentX ID", "/pass\""], ["Sent directly to your phone", "/crew/"]),
    ("crew", 4, ["Every member of your group", "/crew/", "Set up your crew"], ["Sent directly to your phone"]),
])
def test_winner_email_matches_the_reward(client, db_session, sent_mail, kind, crew_size, expect, leave_out):
    from flask import render_template
    from app.drops.service import run_pick

    campaign, drops = make_campaign([(-1, kind, 1, crew_size)])
    student = make_student("winner@example.com", first="Wanjiru")
    assert join(client, login(client, student)).status_code == 201
    backdate_membership(campaign, student, 10)
    run_pick(drops[0].id, "test")

    [mail] = sent_mail
    assert mail["subject"] == "Congratulations! Your StudentXmas Reward is UNLOCKED!"
    pick = mail["context"]["pick"]
    html = render_template("email/drop_picked.html", frontend_url="https://studentx.co.ke", context=mail["context"])
    assert "Hey Wanjiru," in html
    assert mail["context"]["valid_until"] == pick.expires_at.strftime("%d/%m/%Y") and mail["context"]["valid_until"] in html
    for text in expect:
        assert text in html, text
    for text in leave_out:
        assert text not in html, text
    if kind != "airtime":
        assert pick.reference in html
