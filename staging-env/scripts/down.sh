#!/usr/bin/env bash
# Stop staging. With --wipe, also delete its database so the next start is fresh.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" = "--wipe" ]; then
  docker compose --env-file .state/compose.env down -v
else
  docker compose --env-file .state/compose.env down
fi
