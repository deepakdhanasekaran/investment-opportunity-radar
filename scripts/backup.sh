#!/bin/sh
# Usage: scripts/backup.sh [dir]   (cron: 0 3 * * * /path/scripts/backup.sh)  Keeps 14 days.
set -e
D="${1:-./backups}"; mkdir -p "$D"
F="$D/radar-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose exec -T db pg_dump -U radar radar | gzip > "$F"
[ -s "$F" ] || { echo "empty backup" >&2; rm -f "$F"; exit 1; }
find "$D" -name 'radar-*.sql.gz' -mtime +14 -delete
echo "$F"
