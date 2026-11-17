#!/usr/bin/env bash
# Start (or refresh) the staging environment.
#
#   staging-env/scripts/up.sh [path-to-student-site-repo] [git-ref]
#
# Defaults: ../studentx next to this repo's parent folder, ref "master"
# (what production serves). Secrets, certificate and the site build live in
# staging-env/.state/, which is not committed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$HERE/.state"
FRONTEND_REPO="${1:-$HERE/../../../studentx}"
FRONTEND_REF="${2:-master}"
mkdir -p "$STATE/certs" "$STATE/results"

secret() { python3 -c 'import secrets; print(secrets.token_urlsafe(48))'; }

# Staging-only values, never production's.
if [ ! -f "$STATE/compose.env" ]; then
  cat > "$STATE/compose.env" <<EOF
DB_PASSWORD=$(secret)
DB_ROOT_PASSWORD=$(secret)
EOF
fi
if [ ! -f "$STATE/api.env" ]; then
  cat > "$STATE/api.env" <<EOF
SECRET_KEY=$(secret)
JWT_SECRET_KEY=$(secret)
SECURITY_PASSWORD_SALT=$(secret)
STAGING_ADMIN_PASSWORD=$(secret)
STAGING_MERCHANT_PASSWORD=$(secret)
EOF
fi
chmod 600 "$STATE"/*.env

if [ ! -f "$STATE/certs/localhost.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    -keyout "$STATE/certs/localhost.key" -out "$STATE/certs/localhost.crt" 2>/dev/null
fi

if [ ! -f "$STATE/frontend-dist/index.html" ]; then
  "$HERE/scripts/build-frontend.sh" "$FRONTEND_REPO" "$FRONTEND_REF"
fi

export REVISION="$(git -C "$HERE/.." rev-parse HEAD)"
cd "$HERE"
docker compose --env-file "$STATE/compose.env" up -d --build --wait
docker compose --env-file "$STATE/compose.env" exec -T api python staging-env/scripts/seed.py

echo
echo "API:          https://localhost:8443  (self-signed certificate)"
echo "Student site: http://localhost:8081"
echo "Captured mail and upload stats: http://localhost:9900/mail, /healthz"
echo "Staging admin and merchant passwords: $STATE/api.env"
