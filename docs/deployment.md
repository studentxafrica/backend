# Deployment

## Where each part runs

| Repository | Production branch | Served from | How it gets there |
| --- | --- | --- | --- |
| `studentxafrica/backend` | `staging` | VPS `161.97.72.130` (`api.studentx.co.ke`) | by hand (see below) |
| `studentxafrica/frontend` | `master` | web host `46.62.173.211` | GitHub Actions build, upload over FTP |
| `studentxafrica/merchant-portal` | `master` | web host `46.62.173.211` | GitHub Actions build, upload over FTP |
| `studentxafrica/admin-portal` | `staging` | web host `46.62.173.211` | GitHub Actions build, upload over FTP |

```
                    ┌──────────── web host 46.62.173.211 ────────────┐
 browser ──HTTPS──▶ │ studentx.co.ke · admin. · merchant. (static)    │
    │               └─────────────────────────────────────────────────┘
    │               ┌──────────── VPS 161.97.72.130 (Ubuntu 24.04) ───┐
    └──HTTPS──────▶ │ nginx (TLS, api.studentx.co.ke)                  │
                    │   └─▶ gunicorn 127.0.0.1:6060, 3 sync workers    │
                    │        systemd: studentx-backend.service         │
                    │        user studentx, /home/studentx/backend     │
                    │        ├─▶ MariaDB 10.11 127.0.0.1:3306          │
                    │        └─▶ Redis 127.0.0.1:6379 (rate limits)    │
                    │   studentx-api-healthcheck.timer (every 5 min)   │
                    │   other unrelated apps share this server         │
                    └──────────────────────────────────────────────────┘
```

The backend service sets `FLASK_ENV=production` in its systemd unit, so it
runs `ProductionConfig`. No Celery worker runs for StudentX, so background
tasks (such as coupon CSV uploads) are queued but never processed.

### Backend deploys

`.github/workflows/deploy.yml` runs the tests on every pull request to
`staging`. On every push to `staging` it runs the tests and, if they pass,
logs in to the backend server as `studentx` over SSH and runs
`deploy/remote-deploy.sh` for that commit. The script:

1. stops if the server checkout has uncommitted changes, or commits that are
   not in the commit being deployed;
2. fast-forwards `/home/studentx/backend` and installs `requirements.txt` if it
   changed;
3. checks the new code starts (settings and imports) before touching the
   running service, and stops without changing anything if it does not;
4. reloads gunicorn gracefully (`kill -HUP` on the master process, which
   `studentx` owns, so no sudo is needed) and waits until `/healthz` reports
   the new commit;
5. rolls back to the previous commit if it never does.

Database migrations are not run by the deploy. They are in
`migrations/versions/` and are applied by hand (see Database migrations
below).

(The old FTP workflow uploaded to the frontend web host, since
`ftp.studentx.co.ke` is `46.62.173.211`, not to the backend server, which runs
no FTP service.)

#### One-time setup

1. Create a key pair for deploys only. Add the public key to
   `/home/studentx/.ssh/authorized_keys` on the backend server.
2. In GitHub (Settings → Secrets and variables → Actions), add:
   - secret `DEPLOY_SSH_KEY`: the private key;
   - secret `DEPLOY_KNOWN_HOSTS`: the output of
     `ssh-keyscan -t ed25519 161.97.72.130`. Its fingerprint must be
     `SHA256:pnbP5USeFyJBudvxuiKJAYk5Ftn4bL0yGR7AxGR0oB0`; check with
     `ssh-keygen -lf <file>`;
   - variable `DEPLOY_HOST`: `161.97.72.130`;
   - variable `DEPLOY_USER`: `studentx`.
3. The workflow runs in a GitHub environment named `production`. Add required
   reviewers to it if deploys should wait for approval.

#### Deploying by hand

Run the same script from your machine:

```sh
ssh studentx@161.97.72.130 "bash -s -- $(git rev-parse origin/staging)" < deploy/remote-deploy.sh
```

### Backend `master`

`master` is not deployed. It has three commits that are not on `staging`, and
all three only edit the old deploy workflow. No application code exists only
on `master`. To bring it back in line, merge `staging` into `master` (or reset
`master` to `staging`).

## Knowing what is running

`GET /healthz` returns the commit the running process was started from:

```json
{"status": "ok", "revision": "3f2c1a9..."}
```

The commit is taken from a `REVISION` file next to `run.py` if one exists,
otherwise from the git checkout. It is read once at startup, so the value only
changes after a restart. `unknown` means neither was available. If the code is
copied rather than checked out, write the commit to `REVISION` when deploying.

### Rollback point

Recorded on 2026-11-16, before the first automated deploy: production was a
git checkout of `staging` at `c5d9e91`, plus an uncommitted change to
`app/models/offer.py` (longer offer titles and descriptions).

`c5d9e91` and the two commits under it (`f09956b`, `f31903f fix: Cloudinary
upload issue`) existed only on the server, not on GitHub. The release branch
is built on `c5d9e91` and includes the `offer.py` change, so merging it into
`staging` puts all of that on GitHub.

To go back, run the deploy script with the earlier commit on a branch that
contains it, or on the server run `git reset --hard <commit>` and then
`kill -HUP $(systemctl show -p MainPID --value studentx-backend)`.

### First deploy of this release

1. Run `docs/merchant-audit.sql` and approve legitimate merchants.
2. Add `SECRET_KEY`, `JWT_SECRET_KEY` and `SECURITY_PASSWORD_SALT` to the
   server's `.env` (see below). The deploy refuses to go ahead without them.
3. On the server, discard the uncommitted `app/models/offer.py` change
   (`git checkout -- app/models/offer.py`); the release contains it.
4. Merge into `staging`. The workflow deploys it.

## Database migrations

Production's schema was created before migrations were kept in git. The
first four files in `migrations/versions/` are copied unchanged from the
production server, whose database is at `8d731acd55df`. Later migrations
build on that.

The deploy applies new migrations itself, after checking the new code
starts and before it takes traffic. If a migration fails, the code is put
back and production keeps running the previous commit. So migrations must
only add (new tables, new columns with defaults): the old code keeps
running until the reload.

Before merging a change that includes a migration, back up the database as
the app user on the server:

```sh
mariadb-dump --single-transaction <database> | gzip > ~/pre-migration-$(date +%F).sql.gz
```

To check or apply migrations by hand:

```sh
cd ~/backend
FLASK_ENV=production .venv/bin/alembic current        # expect 8d731acd55df or later
FLASK_ENV=production .venv/bin/alembic upgrade head
```

`.venv/bin/alembic downgrade -1` undoes the last one. `f3d1c0a7e2b9`
(Festive Drops) only creates new tables, so undoing it removes them and
their data. `b7e4c2d91f30` adds the promotional email consent to members
and opts in everyone who already has an account.

## Festive Drops picks

An admin picks each drop's winners by hand, from the StudentXmas screen in
the admin portal ("Pick winners"), at or after the drop's pick time. The
pick is random among verified members who joined before that time, and
winners are emailed straight away. The screen flags drops that are ready to
pick. The same pick is available as
`POST /api/v1/drops/admin/drops/<id>/pick` or `flask drops run-due` (which
picks every drop whose time has passed).

Other commands: `flask drops seed-studentxmas` creates the campaign;
`flask drops set-venue-pin <drop-id>` sets the PIN a venue uses to mark
passes as used.

Run every `flask` and `alembic` command on the server as the app user, from
`~/backend`, with the production settings; without `FLASK_ENV=production`
they start with the development settings instead:

```sh
FLASK_ENV=production .venv/bin/flask --app wsgi drops seed-studentxmas
```

## Promotional email (Brevo)

The backend sends transactional email only (Mailtrap). Promotional email is
sent from Brevo, to the members who agreed to it. Members who had an account
before consent was asked are opted in; new members opt in at sign-up, and
anyone can change it on their profile.

The backend keeps one Brevo list in step with that consent. Only consenting
members are sent to Brevo (email, first and last name, member id). Add to
the server's `.env`:

| Setting | Value |
| --- | --- |
| `BREVO_API_KEY` | an API key from Brevo > SMTP & API > API keys |
| `BREVO_LIST_ID` | the id of the members list |
| `BREVO_WEBHOOK_TOKEN` | a random value (as for the signing secrets below) |

Then:

1. Restart the application, and run `FLASK_ENV=production .venv/bin/flask --app wsgi brevo sync --dry-run`
   to see what will be sent, then `FLASK_ENV=production .venv/bin/flask --app wsgi brevo sync` to add every
   consenting member to the list.
2. In Brevo > Settings > Webhooks, add a marketing webhook to
   `https://api.studentx.co.ke/api/v1/integrations/brevo/webhook` for the
   "Unsubscribed" and "Marked as spam" events, with bearer authentication
   using `BREVO_WEBHOOK_TOKEN`. Members who unsubscribe from a campaign are
   then opted out on StudentX too.

After that, sign-ups and profile changes reach Brevo within seconds. Run
`brevo sync` again before each campaign to pick up anything missed (for
example while Brevo was unreachable); it is safe to run at any time.

## Signing secrets

The backend will not start unless these are set in the environment or `.env`.
Each must be at least 32 characters long.

| Setting | Used for |
| --- | --- |
| `SECRET_KEY` | Flask sessions, email-confirmation and password-reset links |
| `JWT_SECRET_KEY` | login sessions (access-token cookies) |
| `SECURITY_PASSWORD_SALT` | separating email-confirmation and password-reset links |

Generate a value with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use different values in each environment, and never commit them. Any value
that has ever appeared in git history must be treated as compromised.

For local development, add the three settings to your own `.env`.

### Rotating the secrets

1. Generate three new values and put them in the server's `.env`. Do not paste
   them into tickets, chat or CI logs.
2. Deploy, then restart the application.
3. Check that `/healthz` shows the new revision.
4. Check that an old session no longer works. A browser that was logged in
   before the rotation should be sent back to the login page.

Rotating the keys, and this release itself, signs everyone out once.
Password-reset and email-confirmation links sent before the release stop
working, and users need to request a new one.

## Merchant registration and approval

Only a signed-in administrator can create merchant accounts
(`POST /api/v1/admin/merchants/register`). Students only see offers from
merchants an administrator has approved. Offers from merchants who are not
yet approved stay hidden, but they are not deleted.

**Before deploying**, run `docs/merchant-audit.sql` against production and
approve every legitimate merchant that has live offers. Until a merchant is
approved, its offers disappear from the student site.

The same query lists every merchant with its creation date. Registration did
not require a login before this change, and nothing records who created each
account. Review the list with the founders to confirm each merchant is
genuine.
