# Staging environment

A copy of production that runs on one machine with Docker, for testing
changes and checking behaviour before it reaches students. It runs:

| Part | Staging | Production |
| --- | --- | --- |
| API | This checkout, `FLASK_ENV=production`, gunicorn 23 with 3 workers (`GUNICORN_WORKERS`) and a 120 s timeout | Same |
| Python | 3.12 | 3.12.3 |
| Database | MariaDB 10.11, schema created from the models | MariaDB 10.11.14 |
| Rate limits | Redis 7.0 | Redis 7.0.15 |
| Proxy | nginx 1.24 with the production site settings (10 MB upload limit, forwarded client address), self-signed certificate | nginx with Let's Encrypt |
| Student site | Built from the student-site repo at `master`, pointed at this API | `studentx.co.ke` |
| Cloudinary | Local stand-in that answers after 2 s (`UPLOAD_DELAY`) | Cloudinary |
| Mailtrap | Local stand-in that keeps every email for tests to read | Mailtrap |

The API container is limited to 2 CPUs (`API_CPUS`). Production has 4 CPUs,
shared with other applications, so treat capacity results as indicative.

Nothing here talks to production, Cloudinary or Mailtrap, and it uses its own
secrets and passwords, generated on first start.

## Start and stop

```sh
staging-env/scripts/up.sh [path-to-student-site-repo] [git-ref]
staging-env/scripts/down.sh          # stop, keep data
staging-env/scripts/down.sh --wipe   # stop and delete the database
```

| Address | What |
| --- | --- |
| https://localhost:8443 | API through nginx (accept the self-signed certificate) |
| http://localhost:8081 | Student site |
| http://localhost:6060 | API directly, for load tests |
| http://localhost:9900/mail | Emails the API has sent |

The staging admin (`staging-admin`) and merchant (`shopzetu@staging.invalid`)
passwords are in `staging-env/.state/api.env`. To rebuild the student site
from another branch, delete `.state/frontend-dist` and run `up.sh` again with
the ref.

## Tests

| Test | Command | What it shows |
| --- | --- | --- |
| Backend suite on MariaDB | see below | The pytest suite against the production database engine |
| Student journey | `docker compose --env-file .state/compose.env exec -T api python staging-env/tests/journey.py` | Sign-up, ID upload, admin approval, entering an offer, the merchant's entrant list, password reset, merchant registration, rate limits |
| Student site in a browser | see below | What the real sign-up screens send to the API |
| Campaign load | `staging-env/scripts/load-test.sh <workers> <peak> ...` | Students signing up and uploading IDs at the same moment while others browse |
| Backup and restore | `staging-env/scripts/backup-drill.sh` | A dump restores to identical row counts, and how long each takes |

Results are written to `staging-env/.state/results/`. In the journey output,
`FINDING` means the behaviour matches a known problem in the Audit Findings
Register; `FAIL` means something that should work did not.

Backend suite on MariaDB (run from `staging-env/`):

```sh
set -a; . .state/compose.env; set +a
docker compose --env-file .state/compose.env exec -T \
  -e TEST_DATABASE_URL="mysql+pymysql://studentx:${DB_PASSWORD}@db:3306/studentx_test" \
  api python -m pytest -q -p no:cacheprovider
```

The two revision tests fail inside the container because it has no `git`
command; they pass where git is installed, as in GitHub Actions.

Student site in a browser:

```sh
docker run --rm --network host -v "$PWD/tests/browser:/t" -v "$PWD/.state/results:/results" \
  -e RESULTS_DIR=/results -w /t mcr.microsoft.com/playwright:v1.56.1-noble \
  sh -c 'npm install --no-audit --no-fund --loglevel=error && node signup.mjs'
```

## Backups in production

`backup-drill.sh` uses the same two commands that would back up and restore
production. On the production server, as an admin:

```sh
mariadb-dump --single-transaction --routines --triggers <database> | gzip > studentx-$(date +%F).sql.gz
gunzip -c studentx-YYYY-MM-DD.sql.gz | mariadb <restore-database>
```
