"""
Festive Drops API: the campaign page, joining, picks, crews and live passes.

Public responses never include other members' names or contact details.
"""
from flask import g, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app import db, limiter
from app.drops import service
from app.drops.service import DropError, utcnow
from app.models import Consumer
from app.models.campaign import (FULFILMENT_STATUS, Campaign, CampaignMember,
                                 CrewMember, Drop, DropPick)
from app.models.consumer import VerificationRequestStatus
from app.phone import mask_phone
from app.utils import roles_required

from . import drops


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _error(err: DropError):
    body = {"message": err.message}
    if err.description:
        body["description"] = err.description
    return jsonify(body), err.status


def _viewer() -> Consumer | None:
    """The signed-in student, if any. The campaign page is public."""
    try:
        verify_jwt_in_request(optional=True, locations=["cookies", "headers"])
        identity = get_jwt_identity()
    except Exception:
        return None
    if not identity:
        return None
    return db.session.get(Consumer, identity)


def _campaign_or_404(slug):
    campaign = db.session.query(Campaign).filter_by(slug=slug).first()
    if not campaign:
        raise DropError("Campaign not found", 404)
    return campaign


def _member_state(consumer, member):
    """visitor (signed out), signed_in (has an account, hasn't joined) or joined."""
    if consumer is None:
        return "visitor"
    return "joined" if member else "signed_in"


def _verification_state(consumer):
    if consumer is None:
        return None
    if consumer.verified:
        return "verified"
    if consumer.verification_status in (VerificationRequestStatus.IN_PROGRESS, VerificationRequestStatus.REQUESTED):
        return "in_review"
    if consumer.verification_status == VerificationRequestStatus.REJECTED:
        return "rejected"
    return "unverified"


def _drop_json(drop: Drop, member: CampaignMember | None, my_pick_drop_ids: set, next_id: str | None,
               number: int, total: int, consumer: Consumer | None = None):
    ended = drop.status == "picked"
    result = None
    if ended:
        if drop.id in my_pick_drop_ids:
            result = "picked"
        elif member and member.joined_at <= drop.pick_at:
            verified_in_time = (consumer is not None and consumer.verified
                                and consumer.verified_at is not None and consumer.verified_at <= drop.pick_at)
            result = "not_picked" if verified_in_time else "not_verified"
        elif consumer is not None:
            result = "not_in"
    return {
        "id": drop.id,
        "number": number,
        "total": total,
        "title": drop.title,
        "brand": drop.brand,
        "description": drop.description,
        "coverImage": drop.cover_image,
        "kind": drop.kind,
        "quantity": drop.quantity,
        "crewSize": drop.crew_size,
        "pickAt": _iso(drop.pick_at),
        "useWithinDays": drop.use_within_days,
        "status": "ended" if ended else "upcoming",
        "isNext": drop.id == next_id,
        "pickedCount": drop.run.picked_count if ended and drop.run else None,
        "result": result,
    }


def _campaign_view(campaign: Campaign, consumer: Consumer | None):
    member = service.membership(campaign, consumer) if consumer else None
    my_picks = (db.session.query(DropPick).filter_by(campaign_id=campaign.id, consumer_id=consumer.id).all()
                if consumer else [])
    my_pick_drop_ids = {p.drop_id for p in my_picks}
    drops_ = sorted(campaign.drops, key=lambda d: d.pick_at)
    numbers = {d.id: i + 1 for i, d in enumerate(drops_)}
    upcoming = [d for d in drops_ if d.status == "upcoming"]
    ended = sorted((d for d in drops_ if d.status == "picked"), key=lambda d: d.pick_at, reverse=True)
    next_id = upcoming[0].id if upcoming else None

    def as_json(d):
        return _drop_json(d, member, my_pick_drop_ids, next_id, numbers[d.id], len(drops_), consumer)
    upcoming_json = [as_json(d) for d in upcoming]
    ended_json = [as_json(d) for d in ended]
    return {
        "campaign": {
            "slug": campaign.slug, "name": campaign.name,
            "startsAt": _iso(campaign.starts_at), "endsAt": _iso(campaign.ends_at),
            "termsVersion": campaign.terms_version,
        },
        "member": {
            "state": _member_state(consumer, member),
            "verification": _verification_state(consumer),
            "joinedAt": _iso(member.joined_at) if member else None,
            "phone": mask_phone(consumer.phone) if consumer else None,
            "hasPhone": bool(consumer and consumer.phone),
            "picks": len(my_picks),
        },
        "nextDrop": upcoming_json[0] if upcoming_json else None,
        "latestResult": ended_json[0] if ended_json and member else None,
        "upcoming": upcoming_json,
        "ended": ended_json,
    }


@drops.get('/campaigns/<slug>')
def get_campaign(slug):
    """The campaign page: next drop first, ended drops in their own list."""
    try:
        campaign = _campaign_or_404(slug)
    except DropError as err:
        return _error(err)
    return jsonify({"data": _campaign_view(campaign, _viewer())}), 200


@drops.get('/campaigns/<slug>/drops/<drop_id>')
def get_drop(slug, drop_id):
    try:
        campaign = _campaign_or_404(slug)
    except DropError as err:
        return _error(err)
    view = _campaign_view(campaign, _viewer())
    drop = next((d for d in view["upcoming"] + view["ended"] if d["id"] == drop_id), None)
    if not drop:
        return jsonify({"message": "Drop not found"}), 404
    return jsonify({"data": {"drop": drop, "member": view["member"], "nextDrop": view["nextDrop"],
                             "campaign": view["campaign"]}}), 200


@drops.post('/campaigns/<slug>/join')
@roles_required('consumer')
def join(slug):
    data = request.get_json(silent=True) or {}
    try:
        campaign = _campaign_or_404(slug)
        _, created = service.join_campaign(campaign, g.user, bool(data.get("acceptTerms")), data.get("phone"))
    except DropError as err:
        db.session.rollback()
        return _error(err)
    return jsonify({"message": "You're in every remaining drop" if created else "You've already joined",
                    "data": _campaign_view(campaign, g.user)}), 201 if created else 200


def _pick_json(pick: DropPick):
    drop = pick.drop
    friends = [{
        "firstName": m.consumer.first_name,
        "initials": (m.consumer.first_name[:1] + (m.consumer.last_name or "")[:1]).upper(),
        "status": "verified" if m.consumer.verified else (
            "in_review" if m.consumer.verification_status in (
                VerificationRequestStatus.IN_PROGRESS, VerificationRequestStatus.REQUESTED) else "unverified"),
    } for m in pick.crew]
    return {
        "id": pick.id,
        "drop": {"id": drop.id, "title": drop.title, "brand": drop.brand, "kind": drop.kind,
                 "pickAt": _iso(drop.pick_at), "crewSize": drop.crew_size},
        "pickedAt": _iso(pick.picked_at),
        "expiresAt": _iso(pick.expires_at),
        "reference": pick.reference,
        "fulfilment": pick.fulfilment_status,
        "redeemedAt": _iso(pick.redeemed_at),
        "crewCode": pick.crew_code,
        "crew": friends,
        "crewComplete": service.crew_complete(pick),
        "passAvailable": service.pass_available(pick),
        "phone": mask_phone(pick.consumer.phone) if drop.kind == "airtime" else None,
    }


@drops.get('/me/picks')
@roles_required('consumer')
def my_picks():
    picks = (db.session.query(DropPick).filter_by(consumer_id=g.user.id)
             .order_by(DropPick.picked_at.desc()).all())
    return jsonify({"data": [_pick_json(p) for p in picks]}), 200


def _owned_pick(pick_id, allow_crew=False):
    pick = db.session.get(DropPick, pick_id)
    if not pick:
        raise DropError("Perk not found", 404)
    is_owner = pick.consumer_id == g.user.id
    in_crew = allow_crew and any(m.consumer_id == g.user.id for m in pick.crew)
    if not (is_owner or in_crew):
        raise DropError("Perk not found", 404)
    return pick


@drops.get('/picks/<pick_id>')
@roles_required('consumer')
def get_pick(pick_id):
    try:
        pick = _owned_pick(pick_id, allow_crew=True)
    except DropError as err:
        return _error(err)
    return jsonify({"data": _pick_json(pick)}), 200


@drops.get('/picks/<pick_id>/pass')
@roles_required('consumer')
def get_pass(pick_id):
    """The live pass: a code that changes every 30 seconds, generated here."""
    try:
        pick = _owned_pick(pick_id, allow_crew=True)
    except DropError as err:
        return _error(err)
    if not service.pass_available(pick):
        return jsonify({"message": "Your pass is issued once everyone in your crew is verified"}), 409
    now = utcnow()
    holder = pick.consumer
    return jsonify({"data": {
        "code": service.pass_code(pick, now),
        "secondsLeft": service.seconds_left_in_window(now),
        "serverTime": _iso(now),
        "holder": {"firstName": holder.first_name, "lastName": holder.last_name, "school": holder.school},
        "crew": [m.consumer.first_name for m in pick.crew],
        "drop": {"title": pick.drop.title, "brand": pick.drop.brand, "kind": pick.drop.kind},
        "reference": pick.reference,
        "expiresAt": _iso(pick.expires_at),
        "redeemedAt": _iso(pick.redeemed_at),
    }}), 200


@drops.get('/crew/<code>')
def crew_invite(code):
    """What a friend sees when they open a crew link. First name only."""
    pick = db.session.query(DropPick).filter_by(crew_code=code).first()
    if not pick:
        return jsonify({"message": "This crew link isn't valid"}), 404
    drop = pick.drop
    return jsonify({"data": {
        "inviterFirstName": pick.consumer.first_name,
        "drop": {"title": drop.title, "brand": drop.brand, "crewSize": drop.crew_size},
        "spotsLeft": max(0, drop.crew_size - 1 - len(pick.crew)),
        "expiresAt": _iso(pick.expires_at),
    }}), 200


@drops.post('/crew/<code>/join')
@roles_required('consumer')
def join_crew(code):
    try:
        service.join_crew(code, g.user)
    except DropError as err:
        db.session.rollback()
        return _error(err)
    return jsonify({"message": "You're in the crew"}), 201


@drops.get('/passes/check')
@limiter.limit("30 per minute")
def check_pass():
    """For venues: is this pass code live and unused? No account needed."""
    pick = service.find_pass(request.args.get("code", ""))
    if not pick:
        return jsonify({"data": {"valid": False, "reason": "That code isn't valid. Ask the student to refresh their pass."}}), 200
    now = utcnow()
    reason = None
    if pick.redeemed_at:
        reason = "Already used"
    elif now >= pick.expires_at:
        reason = "Expired"
    elif not service.pass_available(pick):
        reason = "Crew not complete"
    return jsonify({"data": {
        "valid": reason is None,
        "reason": reason,
        "firstName": pick.consumer.first_name,
        "perk": pick.drop.title,
        "brand": pick.drop.brand,
        "crewSize": pick.drop.crew_size,
        "reference": pick.reference,
        "expiresAt": _iso(pick.expires_at),
    }}), 200


@drops.post('/passes/redeem')
@limiter.limit("10 per minute")
def redeem_pass():
    data = request.get_json(silent=True) or {}
    try:
        pick = service.redeem_pass(data.get("code", ""), data.get("pin", ""))
    except DropError as err:
        db.session.rollback()
        return _error(err)
    return jsonify({"message": "Marked as used", "data": {"reference": pick.reference, "redeemedAt": _iso(pick.redeemed_at)}}), 200


# Admin -----------------------------------------------------------------

@drops.post('/admin/drops/<drop_id>/pick')
@roles_required('admin')
def admin_pick(drop_id):
    try:
        run = service.run_pick(drop_id, triggered_by=f"admin:{g.user.username}")
    except DropError as err:
        db.session.rollback()
        return _error(err)
    return jsonify({"data": {"ranAt": _iso(run.ran_at), "eligible": run.eligible_count,
                             "picked": run.picked_count, "shortfall": run.shortfall,
                             "eligibleDigest": run.eligible_digest}}), 200


@drops.get('/admin/campaigns/<slug>/picks')
@roles_required('admin')
def admin_picks(slug):
    """Recipients and what is owed to them, for fulfilment."""
    try:
        campaign = _campaign_or_404(slug)
    except DropError as err:
        return _error(err)
    picks = (db.session.query(DropPick).join(Drop).filter(DropPick.campaign_id == campaign.id)
             .order_by(Drop.pick_at, DropPick.picked_at).all())
    members = db.session.query(CampaignMember).filter_by(campaign_id=campaign.id).count()
    return jsonify({"data": {
        "members": members,
        "picks": [{
            "id": p.id, "dropId": p.drop_id, "drop": p.drop.title, "kind": p.drop.kind,
            "pickAt": _iso(p.drop.pick_at),
            "name": f"{p.consumer.first_name} {p.consumer.last_name}", "email": p.consumer.email,
            "phone": p.consumer.phone, "reference": p.reference, "fulfilment": p.fulfilment_status,
            "crew": [f"{m.consumer.first_name} {m.consumer.last_name}" for m in p.crew],
            "crewComplete": service.crew_complete(p), "expiresAt": _iso(p.expires_at),
            "redeemedAt": _iso(p.redeemed_at),
        } for p in picks],
    }}), 200


@drops.post('/admin/picks/<pick_id>/fulfilment')
@roles_required('admin')
def admin_fulfilment(pick_id):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in FULFILMENT_STATUS.values():
        return jsonify({"message": f"status must be one of {', '.join(FULFILMENT_STATUS.values())}"}), 400
    pick = db.session.get(DropPick, pick_id)
    if not pick:
        return jsonify({"message": "Perk not found"}), 404
    pick.fulfilment_status = status
    pick.fulfilled_at = utcnow() if status == FULFILMENT_STATUS["SENT"] else pick.fulfilled_at
    pick.save()
    return jsonify({"data": {"id": pick.id, "fulfilment": pick.fulfilment_status}}), 200


@drops.post('/admin/drops/<drop_id>/venue-pin')
@roles_required('admin')
def admin_venue_pin(drop_id):
    pin = str((request.get_json(silent=True) or {}).get("pin", ""))
    if len(pin) < 4:
        return jsonify({"message": "Use a PIN of at least 4 digits"}), 400
    drop = db.session.get(Drop, drop_id)
    if not drop:
        return jsonify({"message": "Drop not found"}), 404
    service.set_venue_pin(drop, pin)
    return jsonify({"message": "Venue PIN set"}), 200


@drops.get('/admin/campaigns/<slug>')
@roles_required('admin')
def admin_campaign(slug):
    """Everything the Drops screen needs about the campaign and its drops."""
    try:
        campaign = _campaign_or_404(slug)
    except DropError as err:
        return _error(err)
    members = db.session.query(CampaignMember).filter_by(campaign_id=campaign.id).all()
    verified = sum(1 for m in members if m.consumer.verified)
    now = utcnow()
    drops_ = sorted(campaign.drops, key=lambda d: d.pick_at)
    return jsonify({"data": {
        "campaign": {"slug": campaign.slug, "name": campaign.name,
                     "startsAt": _iso(campaign.starts_at), "endsAt": _iso(campaign.ends_at)},
        "members": len(members),
        "verifiedMembers": verified,
        "drops": [{
            "id": d.id, "number": i + 1, "title": d.title, "brand": d.brand, "description": d.description,
            "coverImage": d.cover_image, "kind": d.kind, "quantity": d.quantity, "crewSize": d.crew_size,
            "pickAt": _iso(d.pick_at), "status": d.status,
            "readyToPick": d.status == "upcoming" and now >= d.pick_at,
            "venuePinSet": bool(d._venue_pin),
            "run": {"ranAt": _iso(d.run.ran_at), "eligible": d.run.eligible_count, "picked": d.run.picked_count,
                    "shortfall": d.run.shortfall, "triggeredBy": d.run.triggered_by} if d.run else None,
        } for i, d in enumerate(drops_)],
    }}), 200


@drops.put('/admin/drops/<drop_id>')
@roles_required('admin')
def admin_edit_drop(drop_id):
    """Edit what students see about a drop. The pick time and quantity stay as set."""
    drop = db.session.get(Drop, drop_id)
    if not drop:
        return jsonify({"message": "Drop not found"}), 404
    data = request.get_json(silent=True) or {}
    for field, column, limit in (("title", "title", 128), ("brand", "brand", 128)):
        if field in data:
            value = str(data[field] or "").strip()
            if not value or len(value) > limit:
                return jsonify({"message": f"{field.capitalize()} must be 1 to {limit} characters"}), 400
            setattr(drop, column, value)
    if "description" in data:
        drop.description = str(data["description"] or "").strip() or None
    if "coverImage" in data:
        image = data["coverImage"]
        if not image:
            drop.cover_image = None
        elif str(image).startswith("http"):
            drop.cover_image = image
        else:
            # A photo picked in the admin portal arrives as a data URL.
            import cloudinary.uploader
            try:
                drop.cover_image = cloudinary.uploader.upload(image, folder="studentx/drops")["secure_url"]
            except Exception as err:
                return jsonify({"message": "Couldn't upload the photo", "description": str(err)[:200]}), 502
    drop.save()
    return jsonify({"message": "Drop updated", "data": {"id": drop.id, "title": drop.title, "brand": drop.brand,
                                                        "description": drop.description, "coverImage": drop.cover_image}}), 200
