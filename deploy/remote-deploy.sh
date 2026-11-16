#!/usr/bin/env bash
# Deploys a staging commit on the backend server. Run as the app user:
#
#   ssh studentx@<host> 'bash -s -- <commit>' < deploy/remote-deploy.sh
#
# Fast-forwards the checkout, installs changed requirements, checks the new
# code can start, reloads gunicorn gracefully, and waits until every worker
# reports the new commit. Anything that fails before the reload leaves
# production untouched; a failed reload is rolled back to the previous commit.
#
# The script arrives on stdin, so every command that could read stdin is given
# /dev/null instead.
set -euo pipefail

TARGET="${1:?usage: remote-deploy.sh <commit>}"
APP_DIR="${APP_DIR:-$HOME/backend}"
SERVICE="${SERVICE:-studentx-backend}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:6060/healthz}"
BRANCH="${BRANCH:-staging}"

cd "$APP_DIR"
log() { echo "[deploy] $*"; }
fail() { echo "::error::$*"; exit 1; }

# 1. Refuse to overwrite anything changed by hand on the server.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  git status --short --untracked-files=no
  fail "The server checkout has uncommitted changes (listed above). Commit them to $BRANCH or discard them, then deploy again."
fi

PREVIOUS="$(git rev-parse HEAD)"
log "Running $PREVIOUS, deploying $TARGET"

git fetch --quiet origin "$BRANCH" </dev/null
git cat-file -e "$TARGET^{commit}" 2>/dev/null || fail "$TARGET is not on origin/$BRANCH."

if [ "$PREVIOUS" = "$TARGET" ]; then
  log "Already at $TARGET; reloading anyway."
elif ! git merge-base --is-ancestor "$PREVIOUS" "$TARGET"; then
  git log --oneline "$TARGET..$PREVIOUS" | head -20
  fail "Production has commits that are not in $TARGET (listed above). Push them to $BRANCH first."
fi

install_requirements() {
  local from="$1" to="$2"
  if [ "$from" != "$to" ] && ! git diff --quiet "$from" "$to" -- requirements.txt; then
    log "requirements.txt changed; installing"
    .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt </dev/null
  fi
}

reload_gunicorn() {
  local pid
  pid="$(systemctl show -p MainPID --value "$SERVICE")"
  if [ -z "$pid" ] || [ "$pid" = "0" ]; then
    log "$SERVICE is not running; systemd will start it with the current code."
    return 0
  fi
  log "Reloading gunicorn (pid $pid)"
  kill -HUP "$pid"
}

# What /healthz reports: the commit, "none" if the running code predates the
# revision field, or "unreachable" if it does not answer.
reported_revision() {
  curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null \
    | .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); print(d.get("revision") or "none") if d.get("status")=="ok" else print("unhealthy")' 2>/dev/null \
    || echo unreachable
}

# Wait until several consecutive health checks report the expected commit,
# so old workers still finishing requests have exited. With "or-none",
# code that predates the revision field also counts, as long as it is healthy.
LAST_REPORTED=""
wait_for_revision() {
  local want="$1" accept_none="${2:-}" streak=0
  for _ in $(seq 1 45); do
    LAST_REPORTED="$(reported_revision)"
    if [ "$LAST_REPORTED" = "$want" ] || { [ -n "$accept_none" ] && [ "$LAST_REPORTED" = "none" ]; }; then
      streak=$((streak + 1))
      [ "$streak" -ge 5 ] && return 0
    else
      streak=0
    fi
    sleep 2
  done
  return 1
}

# The app reports this file's commit on /healthz. Written by the deploy so it
# does not depend on git being on the service's PATH.
record_revision() { echo "$1" > REVISION; }

rollback() {
  log "Rolling back to $PREVIOUS"
  git reset --quiet --hard "$PREVIOUS"
  record_revision "$PREVIOUS"
  install_requirements "$TARGET" "$PREVIOUS"
  reload_gunicorn
  if wait_for_revision "$PREVIOUS" or-none; then
    log "Rolled back; production is healthy on $PREVIOUS"
  else
    echo "::error::Rollback could not confirm production is healthy (last /healthz: $LAST_REPORTED). Check: systemctl status $SERVICE"
  fi
}

# 2. Update the code.
git merge --quiet --ff-only "$TARGET"
record_revision "$TARGET"
install_requirements "$PREVIOUS" "$TARGET"

# 3. Check the new code starts (settings, imports) before touching the
#    running service.
if ! FLASK_ENV=production .venv/bin/python -c 'import wsgi' </dev/null >/tmp/studentx-deploy-check.log 2>&1; then
  tail -20 /tmp/studentx-deploy-check.log
  git reset --quiet --hard "$PREVIOUS"
  record_revision "$PREVIOUS"
  install_requirements "$TARGET" "$PREVIOUS"
  fail "The new code failed to start (output above). Production was not changed."
fi

# 4. Reload and confirm.
reload_gunicorn
if wait_for_revision "$TARGET"; then
  log "Production is running $TARGET"
else
  reported="$LAST_REPORTED"
  rollback
  fail "Production reported '$reported' instead of $TARGET after the reload, so it was rolled back."
fi
