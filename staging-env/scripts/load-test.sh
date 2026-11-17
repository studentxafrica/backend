#!/usr/bin/env bash
# Run the campaign load test at one or more sign-up peaks, with a given number
# of gunicorn workers (production runs 3).
#
#   staging-env/scripts/load-test.sh <workers> <peak> [<peak> ...]
#   e.g. staging-env/scripts/load-test.sh 3 10 25 50
#
# Summaries go to staging-env/.state/results/load-w<workers>-p<peak>.json.
set -euo pipefail
cd "$(dirname "$0")/.."
WORKERS="${1:?workers}"; shift
set -a; . .state/compose.env; set +a
export REVISION="$(git -C .. rev-parse HEAD)"

GUNICORN_WORKERS="$WORKERS" docker compose --env-file .state/compose.env up -d --wait api >/dev/null
echo "gunicorn workers: $WORKERS, API CPU limit: ${API_CPUS:-2}"

for PEAK in "$@"; do
  out=".state/results/load-w${WORKERS}-p${PEAK}.json"
  k6 run --quiet -e PEAK="$PEAK" -e HOLD="${HOLD:-2m}" -e BROWSE_RATE="${BROWSE_RATE:-10}" \
    --summary-export "$out" tests/k6/campaign-load.js > ".state/results/load-w${WORKERS}-p${PEAK}.txt" 2>&1 || true
  python3 - "$out" "$WORKERS" "$PEAK" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))["metrics"]
def p(name, key):
    m = s.get(name, {})
    return m.get(key, m.get("values", {}).get(key, 0))
signups = p("completed_signups", "count")
failed = p("failed_signups", "count")
checks = s.get("checks", {})
sec = lambda name, key: p(name, key) / 1000
print(f"workers={sys.argv[2]} peak={sys.argv[3]}: {signups:.0f} sign-ups completed, {failed:.0f} failed; "
      f"sign-up p95 {sec('signup_journey', 'p(95)'):.1f}s; ID upload median {sec('id_upload', 'med'):.1f}s, p95 {sec('id_upload', 'p(95)'):.1f}s; "
      f"browsing median {sec('browse', 'med'):.2f}s, p95 {sec('browse', 'p(95)'):.2f}s; "
      f"checks passed {checks.get('passes', 0)}/{checks.get('passes', 0) + checks.get('fails', 0)}")
EOF
done
