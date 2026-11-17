#!/usr/bin/env bash
# Back up the staging database and restore it into a second database, then
# compare row counts table by table. The same two commands work on the
# production server (run as an admin there); see the README.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . .state/compose.env; set +a
dc() { docker compose --env-file .state/compose.env "$@"; }
OUT=.state/results
mkdir -p "$OUT"

started=$(date +%s)
dc exec -T -e MYSQL_PWD="$DB_PASSWORD" db \
  mariadb-dump --single-transaction --routines --triggers -u studentx studentx > "$OUT/backup.sql"
dumped=$(date +%s)
dc exec -T -e MYSQL_PWD="$DB_PASSWORD" db mariadb -u studentx studentx_restore < "$OUT/backup.sql"
restored=$(date +%s)

counts() {
  dc exec -T -e MYSQL_PWD="$DB_PASSWORD" db mariadb -N -u studentx -e "
    SELECT CONCAT('SELECT ''', table_name, ''', COUNT(*) FROM \`$1\`.\`', table_name, '\`;')
    FROM information_schema.tables WHERE table_schema = '$1' ORDER BY table_name" \
  | dc exec -T -e MYSQL_PWD="$DB_PASSWORD" db mariadb -N -u studentx
}
counts studentx > "$OUT/counts-original.txt"
counts studentx_restore > "$OUT/counts-restored.txt"

echo "Backup: $(du -h "$OUT/backup.sql" | cut -f1) in $((dumped - started))s; restore in $((restored - dumped))s"
if diff -q "$OUT/counts-original.txt" "$OUT/counts-restored.txt" >/dev/null; then
  echo "Restore matches: $(wc -l < "$OUT/counts-original.txt") tables, $(awk '{s+=$2} END {print s}' "$OUT/counts-original.txt") rows"
else
  echo "Restore differs:"; diff "$OUT/counts-original.txt" "$OUT/counts-restored.txt"; exit 1
fi
