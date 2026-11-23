#!/usr/bin/env bash
set -euo pipefail
DATABASE_URL_INPUT="${DATABASE_URL_DIRECT:-${DATABASE_URL:-}}"
: "${DATABASE_URL_INPUT:?Set DATABASE_URL_DIRECT or DATABASE_URL}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?Set strong backup passphrase}"
# pg_dump accepts libpq URLs, not SQLAlchemy's +psycopg driver-qualified URL.
PG_DUMP_URL="${DATABASE_URL_INPUT/postgresql+psycopg:\/\//postgresql:\/\/}"
PG_DUMP_URL="${PG_DUMP_URL/postgres:\/\//postgresql:\/\/}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="$(mktemp "/tmp/elephant-${stamp}.XXXXXX.dump")"
trap 'rm -f "$tmp"' EXIT
pg_dump --format=custom --no-owner --file="$tmp" "$PG_DUMP_URL"
gpg --batch --yes --pinentry-mode loopback --symmetric --cipher-algo AES256 \
  --passphrase-fd 3 3<<<"$BACKUP_ENCRYPTION_PASSPHRASE" \
  --output "elephant-${stamp}.dump.gpg" "$tmp"
shred -u "$tmp"
trap - EXIT
echo "Encrypted backup created: elephant-${stamp}.dump.gpg; upload to off-site object storage."
