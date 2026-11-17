"""
Festive Drops: joining a campaign, random picks, crews and the live pass.

All times are naive UTC, matching how the rest of the database stores them.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import func

from app import db
from app.models import Consumer
from app.models.campaign import (DROP_STATUS, FULFILMENT_STATUS, Campaign,
                                 CampaignMember, CrewMember, Drop, DropPick,
                                 DropRun)

PASS_CODE_SECONDS = 30
# How late a pick can be before it counts as missed (alerts, admin screen).
PICK_GRACE = timedelta(minutes=5)
_CODE_ALPHABET = "ACDEFGHJKMNPQRTUVWXY3479"


class DropError(Exception):
    """A request the member can fix; `status` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 400, description: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.description = description


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Joining -----------------------------------------------------------------

def membership(campaign: Campaign, consumer: Consumer) -> CampaignMember | None:
    return db.session.query(CampaignMember).filter_by(
        campaign_id=campaign.id, consumer_id=consumer.id).first()


def join_campaign(campaign: Campaign, consumer: Consumer, accepted_terms: bool,
                  phone: str | None = None) -> tuple[CampaignMember, bool]:
    """
    Add a student to the campaign. Returns (membership, created).

    Any student with an account can join straight away, so joining takes
    seconds. Only members who are verified by a drop's pick time are in that
    pick (see eligible_member_ids).
    """
    existing = membership(campaign, consumer)
    if existing:
        return existing, False
    if utcnow() >= campaign.ends_at:
        raise DropError("This campaign has ended", 400)
    if not accepted_terms:
        raise DropError("Agree to the drop terms to join", 400)
    if phone:
        from app.phone import normalise_kenyan_mobile
        normalised = normalise_kenyan_mobile(phone)
        if not normalised:
            raise DropError("Enter a Kenyan mobile number, like 0712 345 678", 400)
        consumer.phone = normalised
    if not consumer.phone:
        raise DropError("Add your Safaricom number so airtime perks have somewhere to go", 400)

    member = CampaignMember(campaign_id=campaign.id, consumer_id=consumer.id,
                            joined_at=utcnow(), terms_version=campaign.terms_version)
    member.save()
    return member, True


# Picking -----------------------------------------------------------------

def eligible_member_ids(drop: Drop) -> list[str]:
    """
    Verified members who joined before the pick time and have not used up
    their picks in this campaign. Sorted, so the pool's digest is stable.
    """
    campaign = drop.campaign
    picks_so_far = (db.session.query(DropPick.consumer_id, func.count(DropPick.id).label("n"))
                    .filter(DropPick.campaign_id == campaign.id)
                    .group_by(DropPick.consumer_id).subquery())
    from app.models.consumer import VerificationRequestStatus
    rows = (db.session.query(CampaignMember.consumer_id)
            .join(Consumer, Consumer.id == CampaignMember.consumer_id)
            .outerjoin(picks_so_far, picks_so_far.c.consumer_id == CampaignMember.consumer_id)
            .filter(CampaignMember.campaign_id == campaign.id,
                    CampaignMember.joined_at <= drop.pick_at,
                    Consumer.verified_at.isnot(None),
                    Consumer.verification_status == VerificationRequestStatus.APPROVED,
                    func.coalesce(picks_so_far.c.n, 0) < campaign.max_picks_per_member)
            .all())
    return sorted(r[0] for r in rows)


def _new_reference(drop: Drop) -> str:
    prefix = {"airtime": "AT", "voucher": "VC", "crew": "CR"}[drop.kind]
    return f"{prefix}-{secrets.token_hex(3).upper()}"


def run_pick(drop_id: str, triggered_by: str, now: datetime | None = None) -> DropRun:
    """
    Pick the drop's recipients at random. Safe to call more than once: a drop
    that has already been picked returns its existing record.
    """
    now = now or utcnow()
    drop = db.session.query(Drop).filter_by(id=drop_id).with_for_update().first()
    if not drop:
        raise DropError("Drop not found", 404)
    if drop.status == DROP_STATUS["PICKED"]:
        db.session.rollback()
        return drop.run
    if now < drop.pick_at:
        db.session.rollback()
        raise DropError("This drop's pick time hasn't come yet", 400)

    pool = eligible_member_ids(drop)
    chosen = secrets.SystemRandom().sample(pool, min(drop.quantity, len(pool)))
    for consumer_id in chosen:
        DropPick(
            drop_id=drop.id, campaign_id=drop.campaign_id, consumer_id=consumer_id,
            picked_at=now, expires_at=now + timedelta(days=drop.use_within_days),
            reference=_new_reference(drop),
            crew_code=secrets.token_urlsafe(6) if drop.is_crew else None,
            _pass_secret=secrets.token_hex(32),
        )
    run = DropRun(drop_id=drop.id, ran_at=now, eligible_count=len(pool), picked_count=len(chosen),
                  shortfall=drop.quantity - len(chosen),
                  eligible_digest=hashlib.sha256("\n".join(pool).encode()).hexdigest(),
                  triggered_by=triggered_by)
    drop.status = DROP_STATUS["PICKED"]
    db.session.commit()
    current_app.logger.info(
        f"Drop {drop.id} picked by {triggered_by}: {len(chosen)} of {len(pool)} eligible, shortfall {run.shortfall}")
    notify_picked(drop)
    return run


def run_due_picks(triggered_by: str = "scheduler", now: datetime | None = None) -> list[DropRun]:
    """Pick every drop whose pick time has passed."""
    now = now or utcnow()
    due = (db.session.query(Drop.id)
           .filter(Drop.status == DROP_STATUS["UPCOMING"], Drop.pick_at <= now)
           .order_by(Drop.pick_at).all())
    return [run_pick(drop_id, triggered_by, now) for (drop_id,) in due]


def notify_picked(drop: Drop) -> None:
    """Email each newly picked member their reward details (transactional)."""
    from app.email import send_email
    from app.phone import mask_phone
    for pick in drop.picks:
        if pick.notified:
            continue
        consumer = pick.consumer
        send_email(
            to=[consumer.email],
            subject="Congratulations! Your StudentXmas Reward is UNLOCKED!",
            template="email/drop_picked",
            context={
                "name": consumer.first_name,
                "drop": drop,
                "pick": pick,
                "phone": mask_phone(consumer.phone) if consumer.phone else None,
                "valid_until": pick.expires_at.strftime("%d/%m/%Y"),
            },
        )
        pick.notified = True
    db.session.commit()


# Crews -----------------------------------------------------------------

def crew_complete(pick: DropPick) -> bool:
    drop = pick.drop
    if not drop.is_crew:
        return True
    friends = pick.crew
    return len(friends) >= drop.crew_size - 1 and all(f.consumer.verified for f in friends)


def join_crew(code: str, consumer: Consumer) -> CrewMember:
    pick = db.session.query(DropPick).filter_by(crew_code=code).with_for_update().first()
    if not pick:
        raise DropError("This crew link isn't valid", 404)
    drop = pick.drop
    if pick.consumer_id == consumer.id:
        raise DropError("This is your own crew", 400)
    if utcnow() >= pick.expires_at:
        raise DropError("This crew perk has expired", 400)
    existing = next((m for m in pick.crew if m.consumer_id == consumer.id), None)
    if existing:
        db.session.rollback()
        return existing
    if len(pick.crew) >= drop.crew_size - 1:
        raise DropError("This crew is already full", 400)
    if db.session.query(CrewMember).filter_by(drop_id=drop.id, consumer_id=consumer.id).first():
        raise DropError("You're already in a crew for this drop", 400)
    member = CrewMember(pick_id=pick.id, drop_id=drop.id, consumer_id=consumer.id, joined_at=utcnow())
    member.save()
    return member


# Live pass -----------------------------------------------------------------

def pass_available(pick: DropPick) -> bool:
    return pick.drop.kind != "airtime" and crew_complete(pick)


def pass_code(pick: DropPick, at: datetime | None = None) -> str:
    """The pass code for the 30-second window containing `at`."""
    at = at or utcnow()
    window = int(at.replace(tzinfo=timezone.utc).timestamp()) // PASS_CODE_SECONDS
    digest = hmac.new(pick._pass_secret.encode(), str(window).encode(), hashlib.sha256).digest()
    return "".join(_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in digest[:6])


def seconds_left_in_window(at: datetime | None = None) -> int:
    at = at or utcnow()
    return PASS_CODE_SECONDS - int(at.replace(tzinfo=timezone.utc).timestamp()) % PASS_CODE_SECONDS


def find_pass(code: str, at: datetime | None = None) -> DropPick | None:
    """The pick whose pass shows `code` now or in the previous window."""
    at = at or utcnow()
    code = (code or "").replace(" ", "").upper()
    if len(code) != 6:
        return None
    previous = at - timedelta(seconds=PASS_CODE_SECONDS)
    candidates = (db.session.query(DropPick).join(Drop)
                  .filter(Drop.kind != "airtime", DropPick.expires_at > at - timedelta(days=1)).all())
    for pick in candidates:
        if hmac.compare_digest(pass_code(pick, at), code) or hmac.compare_digest(pass_code(pick, previous), code):
            return pick
    return None


def set_venue_pin(drop: Drop, pin: str) -> None:
    from werkzeug.security import generate_password_hash
    drop._venue_pin = generate_password_hash(pin)
    drop.save()


def redeem_pass(code: str, pin: str) -> DropPick:
    from werkzeug.security import check_password_hash
    pick = find_pass(code)
    if not pick:
        raise DropError("That code isn't valid. Ask the student to refresh their pass.", 404)
    drop = pick.drop
    if not drop._venue_pin or not check_password_hash(drop._venue_pin, pin or ""):
        raise DropError("Wrong venue PIN", 403)
    if pick.redeemed_at:
        raise DropError("This pass has already been used", 409)
    if utcnow() >= pick.expires_at:
        raise DropError("This pass has expired", 410)
    if not pass_available(pick):
        raise DropError("This crew isn't complete yet", 400)
    pick.redeemed_at = utcnow()
    pick.fulfilment_status = FULFILMENT_STATUS["REDEEMED"]
    pick.save()
    return pick


def overdue_drops(now: datetime | None = None) -> list[Drop]:
    """Drops still unpicked more than PICK_GRACE after their pick time."""
    now = now or utcnow()
    return (db.session.query(Drop)
            .filter(Drop.status == DROP_STATUS["UPCOMING"], Drop.pick_at < now - PICK_GRACE).all())
