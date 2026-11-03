#!/bin/sh
# Usage: scripts/restore.sh backups/radar-XXXX.sql.gz   -- DESTROYS current data. Stops writers first.
set -e
[ -f "$1" ] || { echo "usage: $0 backup.sql.gz" >&2; exit 1; }
docker compose stop api scheduler
docker compose exec -T db psql -U radar -d postgres -c "DROP DATABASE IF EXISTS radar" -c "CREATE DATABASE radar OWNER radar"
gunzip -c "$1" | docker compose exec -T db psql -U radar -d radar -q
docker compose up -d api scheduler
