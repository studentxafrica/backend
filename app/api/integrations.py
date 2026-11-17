"""Calls from outside services."""
import hmac

from flask import Blueprint, current_app, jsonify, request

from app import db

integrations = Blueprint("integrations", __name__)

# Brevo marketing webhook events that mean "stop sending me promotional email"
_OPT_OUT_EVENTS = {"unsubscribe", "unsubscribed", "spam"}


@integrations.post("/brevo/webhook")
def brevo_webhook():
    """Brevo tells us when a member unsubscribes or marks a campaign as spam."""
    token = current_app.config.get("BREVO_WEBHOOK_TOKEN")
    sent = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(sent, token):
        return jsonify({"message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    events = payload if isinstance(payload, list) else [payload or {}]
    from app.models import Consumer
    changed = 0
    for event in events:
        email = (event.get("email") or "").strip().lower()
        if event.get("event") not in _OPT_OUT_EVENTS or not email:
            continue
        member = Consumer.query.filter(Consumer.email == email).first()
        if member and member.marketing_consent:
            member.set_marketing_consent(False, "unsubscribe_link")
            changed += 1
    db.session.commit()
    return jsonify({"updated": changed}), 200
