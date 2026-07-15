#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

if [ "$#" -ne 2 ] || [ "$2" != "--force" ]; then
  printf '%s\n' "Usage: $0 path/to/exam-prep-ai-YYYYMMDDTHHMMSSZ.tar.gz --force" >&2
  printf '%s\n' "This replaces the current local database and uploaded materials." >&2
  exit 2
fi

archive=$1
if [ ! -f "$archive" ]; then
  printf '%s\n' "Backup archive not found: $archive" >&2
  exit 1
fi

snapshot_name=$(tar -tzf "$archive" | awk -F/ 'NF { print $1; exit }')
case "$snapshot_name" in
  exam-prep-ai-*) ;;
  *)
    printf '%s\n' "Archive does not look like an Exam Prep AI backup." >&2
    exit 1
    ;;
esac

workspace=$(mktemp -d)
cleanup() {
  rm -rf "$workspace"
}
trap cleanup EXIT INT TERM

wait_for_database() {
  attempts=0
  until docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    >/dev/null 2>&1
  do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      printf '%s\n' "PostgreSQL did not become ready within 30 seconds." >&2
      exit 1
    fi
    sleep 1
  done
}

tar -xzf "$archive" -C "$workspace"
snapshot_dir="$workspace/$snapshot_name"
if [ ! -f "$snapshot_dir/database.sql" ] || [ ! -d "$snapshot_dir/uploads" ]; then
  printf '%s\n' "Backup is missing database.sql or uploads/." >&2
  exit 1
fi

printf '%s\n' "Restoring PostgreSQL database..."
# Keep application connections from recreating or locking the database during restore.
docker compose stop backend frontend >/dev/null 2>&1 || true
docker compose up -d db
wait_for_database
# --force is safe here because this script already requires an explicit --force
# confirmation before replacing the local database.
docker compose exec -T db sh -c 'dropdb --if-exists --force -U "$POSTGRES_USER" "$POSTGRES_DB"; createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  < "$snapshot_dir/database.sql"

printf '%s\n' "Restoring uploaded materials..."
docker compose up -d backend
docker compose exec -T backend sh -c 'rm -rf /app/uploads/*'
docker compose cp "$snapshot_dir/uploads/." backend:/app/uploads
docker compose up -d frontend

printf '%s\n' "Restore complete. Open http://localhost:${FRONTEND_PORT:-3003}."
