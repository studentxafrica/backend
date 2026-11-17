"""
`flask drops ...` commands.

    flask drops run-due            pick every drop whose time has come
    flask drops seed-studentxmas   create the StudentXmas campaign and its 12 drops
    flask drops set-venue-pin      set the PIN a venue uses to mark passes as used
"""
from datetime import datetime, timedelta

import click
from flask.cli import AppGroup

drops_cli = AppGroup("drops", help="Festive Drops: picks and campaign setup.")

# 12:00 in Nairobi (EAT, UTC+3) is 09:00 UTC.
_PICK_HOUR_UTC = 9

# From the StudentX Festive Season Promotion Tracker. Quantities are set by management.
STUDENTXMAS_DROPS = [
    ("2026-11-20", "KSh 250 Safaricom airtime", "Safaricom", "airtime", 2, None),
    ("2026-11-23", "KSh 250 Safaricom airtime", "Safaricom", "airtime", 2, None),
    ("2026-11-25", "KSh 1,500 dining voucher", "[Restaurant]", "voucher", 1, None),
    ("2026-11-27", "KSh 250 Safaricom airtime", "Safaricom", "airtime", 2, None),
    ("2026-11-30", "KSh 250 Safaricom airtime", "Safaricom", "airtime", 2, None),
    ("2026-12-02", "Bowling for 4", "Strikerz, Westlands", "crew", 1, 4),
    ("2026-12-04", "KSh 250 Safaricom airtime", "Safaricom", "airtime", 2, None),
    ("2026-12-07", "KSh 250 Safaricom airtime", "Safaricom", "airtime", 2, None),
    ("2026-12-09", "KSh 2,500 ShopZetu voucher", "ShopZetu", "voucher", 1, None),
    ("2026-12-11", "KSh 1,000 Safaricom airtime", "Safaricom", "airtime", 1, None),
    ("2026-12-14", "Bowling + arcade for 4", "Strikerz, Westlands", "crew", 1, 4),
    ("2026-12-18", "Go-karting for 5", "Mad Max", "crew", 1, 5),
]

_DESCRIPTIONS = {
    "airtime": "Airtime from StudentX, credited to the Safaricom number on your profile on the day you're picked.",
    "voucher": "A {brand} voucher from StudentX. Show your StudentX pass at the counter within 10 days.",
    "crew": "A pass for you and {friends} friends at {brand}, from StudentX. Every friend needs a verified StudentX account before the pass is issued.",
}


def _pick_time(day: str) -> datetime:
    return datetime.fromisoformat(day) + timedelta(hours=_PICK_HOUR_UTC)


@drops_cli.command("run-due")
def run_due():
    """Pick every drop whose pick time has passed (admins normally pick from the admin portal)."""
    from app.drops.service import run_due_picks
    runs = run_due_picks(triggered_by="command")
    for run in runs:
        click.echo(f"{run.drop.title} ({run.drop.pick_at:%Y-%m-%d}): picked {run.picked_count} "
                   f"of {run.eligible_count} eligible, shortfall {run.shortfall}")
    if not runs:
        click.echo("No drops due.")


@drops_cli.command("seed-studentxmas")
def seed_studentxmas():
    """Create the StudentXmas campaign and its drops. Re-running changes nothing."""
    from app import db
    from app.models.campaign import Campaign, Drop

    campaign = db.session.query(Campaign).filter_by(slug="studentxmas").first()
    if campaign:
        click.echo(f"StudentXmas already exists with {len(campaign.drops)} drops; nothing changed.")
        return
    campaign = Campaign(slug="studentxmas", name="StudentXmas",
                        starts_at=datetime.fromisoformat("2026-11-18"),
                        ends_at=_pick_time("2026-12-18") + timedelta(minutes=1),
                        terms_version="2026-11-17", max_picks_per_member=1)
    for day, title, brand, kind, quantity, crew_size in STUDENTXMAS_DROPS:
        Drop(campaign_id=campaign.id, title=title, brand=brand, kind=kind, quantity=quantity,
             crew_size=crew_size, pick_at=_pick_time(day), use_within_days=10,
             description=_DESCRIPTIONS[kind].format(brand=brand, friends=(crew_size or 1) - 1))
    db.session.commit()
    click.echo(f"Created StudentXmas with {len(STUDENTXMAS_DROPS)} drops.")


@drops_cli.command("set-venue-pin")
@click.argument("drop_id")
@click.option("--pin", prompt=True, hide_input=True, confirmation_prompt=True)
def set_venue_pin(drop_id, pin):
    """Set the PIN a venue uses to mark passes for one drop as used."""
    from app import db
    from app.drops.service import set_venue_pin as _set
    from app.models.campaign import Drop

    drop = db.session.get(Drop, drop_id)
    if not drop:
        raise click.ClickException("Drop not found")
    _set(drop, pin)
    click.echo(f"Venue PIN set for {drop.title} ({drop.pick_at:%Y-%m-%d}).")
