#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

backup_root=${1:-backups}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
snapshot_name="exam-prep-ai-${timestamp}"
snapshot_dir="${backup_root}/${snapshot_name}"
archive="${backup_root}/${snapshot_name}.tar.gz"

cleanup() {
  rm -rf "$snapshot_dir"
}

mkdir -p "$snapshot_dir/uploads"
trap cleanup EXIT INT TERM

printf '%s\n' "Exporting PostgreSQL database..."
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$snapshot_dir/database.sql"

printf '%s\n' "Copying uploaded materials..."
docker compose cp backend:/app/uploads/. "$snapshot_dir/uploads"

cat > "$snapshot_dir/manifest.txt" <<EOF
format=exam-prep-ai-local-backup
created_at=${timestamp}
database_dump=database.sql
uploads_directory=uploads
EOF

printf '%s\n' "Creating compressed archive..."
tar -C "$backup_root" -czf "$archive" "$snapshot_name"
printf '%s\n' "Backup created: $archive"
