#!/usr/bin/env bash
# Build the student site at a git ref, pointed at the staging API.
#
#   staging-env/scripts/build-frontend.sh <student-site-repo> [git-ref]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:?path to the student site repository}"
REF="${2:-master}"
SRC="$HERE/.state/frontend-src"
OUT="$HERE/.state/frontend-dist"

rm -rf "$SRC" "$OUT" && mkdir -p "$SRC" "$OUT"
git -C "$REPO" archive "$REF" | tar -x -C "$SRC"
echo "Building student site $(git -C "$REPO" rev-parse --short "$REF") ($REF)"

docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp \
  -e VITE_SERVER_HEAD=https://localhost:8443/api/v1 \
  -v "$SRC:/src" -w /src node:22 \
  sh -c 'npm ci --no-audit --no-fund --loglevel=error && npm run build'
cp -r "$SRC/dist/." "$OUT/"
