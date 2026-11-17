"""Keeps the Brevo marketing list in step with members' email consent.

Only members who have agreed to promotional email are sent to Brevo, with
their email, first and last name and member id (EXT_ID). Members who take
consent back are removed from the list. Unsubscribes made in Brevo come
back through the webhook in app/api/integrations.py.

Configuration (all optional; with no key or list the sync does nothing):
    BREVO_API_KEY        API key (Brevo > SMTP & API > API keys)
    BREVO_LIST_ID        id of the members list
    BREVO_API_URL        defaults to https://api.brevo.com/v3
    BREVO_WEBHOOK_TOKEN  bearer token Brevo sends with webhook calls
"""
from __future__ import annotations

import logging
from threading import Thread

import requests
from flask import current_app

log = logging.getLogger(__name__)

IMPORT_CHUNK = 500
REMOVE_CHUNK = 150


class BrevoError(Exception):
    pass


def _config():
    cfg = current_app.config
    return {
        "key": cfg.get("BREVO_API_KEY"),
        "list_id": int(cfg["BREVO_LIST_ID"]) if cfg.get("BREVO_LIST_ID") else None,
        "url": (cfg.get("BREVO_API_URL") or "https://api.brevo.com/v3").rstrip("/"),
    }


def enabled() -> bool:
    c = _config()
    return bool(c["key"] and c["list_id"])


def _call(method: str, path: str, json=None, params=None, ok=(200, 201, 202, 204)):
    c = _config()
    response = requests.request(method, f"{c['url']}{path}", json=json, params=params, timeout=15,
                                headers={"api-key": c["key"], "accept": "application/json"})
    if response.status_code not in ok:
        raise BrevoError(f"{method} {path}: {response.status_code} {response.text[:300]}")
    return response.json() if response.content else {}


def _attributes(consumer) -> dict:
    return {"FIRSTNAME": consumer.first_name or "", "LASTNAME": consumer.last_name or "", "EXT_ID": consumer.id}


# One member ------------------------------------------------------------------

def sync_member(consumer, previous_email: str | None = None, resubscribe: bool = False) -> None:
    """Add a consenting member to the list (or update them); remove one who isn't."""
    if not enabled():
        return
    list_id = _config()["list_id"]
    if previous_email and previous_email.lower() != consumer.email.lower():
        # Brevo keys contacts by email; carry the contact over to the new address
        _call("PUT", f"/contacts/{requests.utils.quote(previous_email)}",
              json={"attributes": {"EMAIL": consumer.email}}, ok=(204, 404))
    if consumer.marketing_consent:
        body = {"email": consumer.email, "attributes": _attributes(consumer),
                "listIds": [list_id], "updateEnabled": True}
        if resubscribe:
            # The member asked for promotional email again after unsubscribing
            body["emailBlacklisted"] = False
        _call("POST", "/contacts", json=body)
    else:
        remove_emails([consumer.email])


def remove_emails(emails: list[str]) -> None:
    if not enabled() or not emails:
        return
    list_id = _config()["list_id"]
    for start in range(0, len(emails), REMOVE_CHUNK):
        # 400 means none of these were on the list, which is the outcome we want
        _call("POST", f"/contacts/lists/{list_id}/contacts/remove",
              json={"emails": emails[start:start + REMOVE_CHUNK]}, ok=(200, 201, 400, 404))


def sync_member_soon(consumer_id: str, previous_email: str | None = None, resubscribe: bool = False) -> None:
    """Sync in the background so sign-up and profile saves don't wait on Brevo.
    A failure is logged; the next full sync puts it right."""
    if not enabled():
        return
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            from app.models import Consumer
            consumer = Consumer.query.get(consumer_id)
            if not consumer:
                return
            try:
                sync_member(consumer, previous_email=previous_email, resubscribe=resubscribe)
            except Exception:  # noqa: BLE001 - reported, then corrected by the full sync
                log.exception("Brevo sync failed for member %s", consumer_id)

    Thread(target=run, daemon=True).start()


# Everyone -------------------------------------------------------------------

def list_contacts() -> dict[str, bool]:
    """Every email on the list, and whether it unsubscribed or complained in Brevo."""
    list_id = _config()["list_id"]
    found, offset = {}, 0
    while True:
        page = _call("GET", f"/contacts/lists/{list_id}/contacts", params={"limit": 500, "offset": offset})
        contacts = page.get("contacts", [])
        for c in contacts:
            found[c["email"].lower()] = bool(c.get("emailBlacklisted"))
        offset += len(contacts)
        if not contacts or offset >= page.get("count", 0):
            return found


def full_sync(db_session, Consumer, dry_run: bool = False) -> dict:
    """Bring the list and the app into line.

    1. Members who unsubscribed in Brevo are opted out here.
    2. Every consenting member is added or updated on the list.
    3. Anyone on the list without consent (or no longer a member) is removed.
    Members who never consented are never sent to Brevo.
    """
    if not enabled():
        raise BrevoError("Set BREVO_API_KEY and BREVO_LIST_ID first.")
    list_id = _config()["list_id"]
    on_list = list_contacts()

    opted_out = 0
    for email, unsubscribed in on_list.items():
        if not unsubscribed:
            continue
        member = Consumer.query.filter(Consumer.email == email).first()
        if member and member.marketing_consent:
            member.set_marketing_consent(False, "unsubscribe_link")
            opted_out += 1
    if dry_run:
        db_session.rollback()
    else:
        db_session.commit()

    consenting = Consumer.query.filter(Consumer.marketing_consent.is_(True)).all()
    keep = {c.email.lower() for c in consenting}
    to_remove = [email for email in on_list if email not in keep]
    if not dry_run:
        for start in range(0, len(consenting), IMPORT_CHUNK):
            chunk = consenting[start:start + IMPORT_CHUNK]
            _call("POST", "/contacts/import", json={
                "listIds": [list_id], "updateExistingContacts": True, "emptyContactsAttributes": False,
                "jsonBody": [{"email": c.email, "attributes": _attributes(c)} for c in chunk],
            })
        remove_emails(to_remove)
    return {"opted_out_from_brevo": opted_out, "on_list": len(consenting), "removed": len(to_remove)}


# flask brevo sync -------------------------------------------------------------

from flask.cli import AppGroup  # noqa: E402
import click  # noqa: E402

brevo_cli = AppGroup("brevo", help="Brevo marketing list")


@brevo_cli.command("sync")
@click.option("--dry-run", is_flag=True, help="Report what would change without changing anything.")
def sync_command(dry_run):
    """Bring the Brevo list and members' email consent into line."""
    from app import db
    from app.models import Consumer
    try:
        result = full_sync(db.session, Consumer, dry_run=dry_run)
    except BrevoError as err:
        raise click.ClickException(str(err))
    prefix = "Would sync" if dry_run else "Synced"
    click.echo(f"{prefix}: {result['on_list']} members on the list, {result['removed']} removed, "
               f"{result['opted_out_from_brevo']} opted out after unsubscribing in Brevo.")
