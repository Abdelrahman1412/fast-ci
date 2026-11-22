#!/usr/bin/env bash
# Build, dump, restore and verify a migrated template database.
#
#   test_db.sh build     migrate a fresh database and dump it
#   test_db.sh restore   restore the dump; exit 3 if it is stale or missing
#   test_db.sh ensure    restore if possible, else build (prints hit / miss / stale)
#
# Settings (environment):
#   FASTCI_BASE_DB       template database name                  (acme_test_base)
#   FASTCI_DUMP          dump file path                          (.cache/test-db/base.dump)
#   FASTCI_FINGERPRINT   expected fingerprint, see fingerprint.py (required)
#   FASTCI_MIGRATE_CMD   command that migrates $DATABASE_URL     (required for build)
#   FASTCI_PG_CONTAINER  run psql/pg_dump/pg_restore inside this Docker container,
#                        so the client tools match the server's major version
#   PGHOST PGPORT PGUSER PGPASSWORD   the usual libpq variables
set -euo pipefail

cmd=${1:-}
base=${FASTCI_BASE_DB:-acme_test_base}
dump=${FASTCI_DUMP:-.cache/test-db/base.dump}
fp=${FASTCI_FINGERPRINT:?set FASTCI_FINGERPRINT (scripts/fingerprint.py prints it)}

now_ms() { echo $(( $(date +%s%N) / 1000000 )); }
# Client tools older than the server refuse to dump it. On CI runners the
# preinstalled client is often a major behind the service container.
pgx() {
  if [ -n "${FASTCI_PG_CONTAINER:-}" ]; then
    docker exec -i -e PGHOST=127.0.0.1 -e PGPORT=5432 -e PGUSER -e PGPASSWORD "$FASTCI_PG_CONTAINER" "$@"
  else
    "$@"
  fi
}

log() { printf 'test-db: %s\n' "$*" >&2; }

url() {
  local auth="${PGUSER:-postgres}"
  [ -n "${PGPASSWORD:-}" ] && auth="$auth:$PGPASSWORD"
  printf 'postgresql://%s@%s:%s/%s' "$auth" "${PGHOST:-127.0.0.1}" "${PGPORT:-5432}" "$1"
}

fresh_db() {
  pgx psql -q -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS \"$base\" WITH (FORCE)" \
    -c "CREATE DATABASE \"$base\""
}

stored_fingerprint() {
  pgx psql -tA -d "$base" -c "SELECT value FROM fastci_meta WHERE key = 'fingerprint'" 2>/dev/null || true
}

build() {
  : "${FASTCI_MIGRATE_CMD:?set FASTCI_MIGRATE_CMD}"
  local started; started=$(now_ms)
  fresh_db
  DATABASE_URL=$(url "$base") bash -c "$FASTCI_MIGRATE_CMD" >&2
  pgx psql -q -d "$base" -v ON_ERROR_STOP=1 \
    -c "CREATE TABLE fastci_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)" \
    -c "INSERT INTO fastci_meta VALUES ('fingerprint', '$fp')"
  mkdir -p "$(dirname "$dump")"
  pgx pg_dump -Fc --no-owner -d "$base" > "$dump"
  log "built $base in $(( $(now_ms) - started )) ms, dumped to $dump ($(du -h "$dump" | cut -f1))"
}

restore() {
  if [ ! -s "$dump" ]; then
    log "no dump at $dump"
    return 3
  fi
  local started; started=$(now_ms)
  fresh_db
  pgx pg_restore --no-owner --exit-on-error -d "$base" < "$dump"
  local got
  got=$(stored_fingerprint)
  if [ "$got" != "$fp" ]; then
    log "dump is stale: it holds fingerprint '${got:-none}', the code expects '$fp'"
    return 3
  fi
  log "restored $base in $(( $(now_ms) - started )) ms"
}

case "$cmd" in
  build) build ;;
  restore) restore ;;
  ensure)
    if [ -s "$dump" ]; then
      if restore; then echo hit; exit 0; fi
      echo stale
    else
      echo miss
    fi
    build
    ;;
  *) echo "usage: $0 build|restore|ensure" >&2; exit 2 ;;
esac
