"""
`flask drops ...` commands.

    flask drops run-due            pick every drop whose time has come
    flask drops seed-studentxmas   create the StudentXmas campaign and its 12 drops
    flask drops set-venue-pin      set the PIN a venue uses to mark passes as used
    flask drops update-studentxmas-wording   apply the tracker's wording to the drops
"""
from datetime import datetime, timedelta

import click
from flask.cli import AppGroup

drops_cli = AppGroup("drops", help="Festive Drops: picks and campaign setup.")

# 12:00 in Nairobi (EAT, UTC+3) is 09:00 UTC.
_PICK_HOUR_UTC = 9

# From the StudentX Festive Season Promotion Tracker. Quantities are set by
# management; wording is in app/drops/studentxmas.py.
STUDENTXMAS_DROPS = [
    # (pick date, kind, quantity, crew size)
    ("2026-11-20", "airtime", 2, None),
    ("2026-11-23", "airtime", 2, None),
    ("2026-11-25", "voucher", 1, None),
    ("2026-11-27", "airtime", 2, None),
    ("2026-11-30", "airtime", 2, None),
    ("2026-12-02", "crew", 1, 4),
    ("2026-12-04", "airtime", 2, None),
    ("2026-12-07", "airtime", 2, None),
    ("2026-12-09", "voucher", 1, None),
    ("2026-12-11", "airtime", 1, None),
    ("2026-12-14", "crew", 1, 4),
    ("2026-12-18", "crew", 1, 5),
]


from app.drops.studentxmas import STUDENTXMAS_TERMS_VERSION  # noqa: E402


def _apply_copy(drop, day: str) -> None:
    from app.drops.studentxmas import STUDENTXMAS_COPY
    copy = STUDENTXMAS_COPY[day]
    drop.title, drop.brand, drop.description = copy["title"], copy["brand"], copy["description"]
    drop.card_badge, drop.card_subtext = copy["badge"], copy["subtext"]


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
                        terms_version=STUDENTXMAS_TERMS_VERSION, max_picks_per_member=1)
    for day, kind, quantity, crew_size in STUDENTXMAS_DROPS:
        drop = Drop(campaign_id=campaign.id, kind=kind, quantity=quantity, crew_size=crew_size,
                    pick_at=_pick_time(day), use_within_days=10)
        _apply_copy(drop, day)
    db.session.commit()
    click.echo(f"Created StudentXmas with {len(STUDENTXMAS_DROPS)} drops.")


@drops_cli.command("update-studentxmas-wording")
@click.option("--dry-run", is_flag=True, help="List what would change without changing anything.")
def update_studentxmas_wording(dry_run):
    """Set every StudentXmas drop's title, brand, badge, subtext and description to
    the tracker's wording, and the terms version students agree to when they join.
    Pick times, quantities, photos and picks are untouched."""
    from app import db
    from app.models.campaign import Campaign

    campaign = db.session.query(Campaign).filter_by(slug="studentxmas").first()
    if not campaign:
        raise click.ClickException("StudentXmas doesn't exist yet; run seed-studentxmas first.")
    changed = 0
    if campaign.terms_version != STUDENTXMAS_TERMS_VERSION:
        click.echo(f"Terms: version {campaign.terms_version} -> {STUDENTXMAS_TERMS_VERSION}")
        campaign.terms_version = STUDENTXMAS_TERMS_VERSION
    for drop in sorted(campaign.drops, key=lambda d: d.pick_at):
        day = drop.pick_at.date().isoformat()
        before = (drop.title, drop.brand, drop.description, drop.card_badge, drop.card_subtext)
        try:
            _apply_copy(drop, day)
        except KeyError:
            click.echo(f"{day}: no wording in the tracker for this date; left as it is.", err=True)
            continue
        after = (drop.title, drop.brand, drop.description, drop.card_badge, drop.card_subtext)
        if before != after:
            changed += 1
            click.echo(f"{day}: {before[0]} -> {after[0]}")
    if dry_run:
        db.session.rollback()
        click.echo(f"Would update {changed} drops.")
    else:
        db.session.commit()
        click.echo(f"Updated {changed} drops.")


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
