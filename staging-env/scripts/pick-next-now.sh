#!/usr/bin/env bash
# Staging only: bring the next upcoming drop's pick time to now and pick it,
# so the 12:00 pick can be tried without waiting for its date.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .state/compose.env exec -T api python - <<'EOF' 2>/dev/null | grep -E "^(Picked|No )"
import sys
sys.path.insert(0, "/app")
from run import app
from app import db
from app.models.campaign import Drop
from app.drops.service import run_pick, utcnow
with app.app_context():
    drop = db.session.query(Drop).filter_by(status="upcoming").order_by(Drop.pick_at).first()
    if not drop:
        print("No upcoming drops left.")
    else:
        drop.pick_at = utcnow()
        db.session.commit()
        run = run_pick(drop.id, "staging:pick-next-now")
        print(f"Picked {drop.title}: {run.picked_count} of {run.eligible_count} eligible members")
EOF
