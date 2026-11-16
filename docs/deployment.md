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

There is no automated backend deploy. The old FTP workflow uploaded to the
frontend web host (`ftp.studentx.co.ke` is `46.62.173.211`), not to the
backend server, and that server runs no FTP service. It has been replaced by
`.github/workflows/tests.yml`, which only runs the test suite on `staging`.

To deploy by hand, as the `studentx` user on the backend server:

1. Update `/home/studentx/backend` to the `staging` commit being released.
2. Install dependencies into `.venv` if `requirements.txt` changed.
3. Restart the service: `sudo systemctl restart studentx-backend`.
4. Check `https://api.studentx.co.ke/healthz` reports that commit.

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

Before the first deploy of this change, record what production is running,
because the version running now cannot report its commit:

1. Copy `/home/studentx/backend` (excluding `.venv`), or snapshot the server.
2. Note the date of that copy and the newest `staging` commit whose code it
   matches. Production already serves `/healthz`, which was added to `staging`
   on 2026-06-01, so it was last updated by hand from `staging`.

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
