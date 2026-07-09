#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3003}"
if [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then
  NEXT_PUBLIC_API_URL="http://localhost:${BACKEND_PORT}"
  export NEXT_PUBLIC_API_URL
fi
if [ -z "${CORS_ORIGINS:-}" ]; then
  CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"
  export CORS_ORIGINS
fi

log() {
  printf '\n==> %s\n' "$1"
}

run_with_timeout() {
  seconds="$1"
  shift

  "$@" &
  command_pid="$!"

  (
    sleep "$seconds"
    kill "$command_pid" 2>/dev/null || true
  ) &
  timer_pid="$!"

  if wait "$command_pid"; then
    status=0
  else
    status="$?"
  fi

  kill "$timer_pid" 2>/dev/null || true
  wait "$timer_pid" 2>/dev/null || true

  if [ "$status" -eq 143 ]; then
    return 124
  fi
  return "$status"
}

check_port_available() {
  port="$1"
  allowed_container="$2"
  label="$3"

  docker_owners="$(
    docker ps --format '{{.Names}}|{{.Ports}}' \
      | grep -E "(0\.0\.0\.0:${port}->|\[::\]:${port}->)" \
      | cut -d '|' -f 1 \
      || true
  )"
  unexpected_owners="$(
    printf '%s\n' "$docker_owners" \
      | grep -v -x "$allowed_container" \
      | grep -v '^$' \
      || true
  )"
  if [ -n "$unexpected_owners" ]; then
    cat >&2 <<EOF
Port ${port} is already used by another Docker container:
${unexpected_owners}

Stop that container or change its port, then run ./scripts/local_verify.sh again.
This script does not remove project volumes.
EOF
    exit 1
  fi

  if [ -z "$docker_owners" ] && command -v lsof >/dev/null 2>&1; then
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/tmp/exam-prep-port-"$port".txt 2>/dev/null; then
      cat >&2 <<EOF
Port ${port} is already in use, so ${label} cannot start.

Current listener:
$(cat /tmp/exam-prep-port-"$port".txt)

Stop that process or change its port, then run ./scripts/local_verify.sh again.
This script does not remove project volumes.
EOF
      exit 1
    fi
  fi
}

log "Checking Docker daemon"
if ! run_with_timeout 30 docker version >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Docker is not responding.

Try this, then run ./scripts/local_verify.sh again:
  1. Open or restart Docker Desktop.
  2. Wait until Docker Desktop says it is running.
  3. Confirm the daemon responds with: docker version

This script does not remove project volumes, so your local study data is preserved.
EOF
  exit 1
fi

log "Validating Docker Compose configuration"
docker compose config --quiet

log "Checking local ports"
check_port_available "$BACKEND_PORT" exam-prep-ai-backend-1 "the backend API"
check_port_available "$FRONTEND_PORT" exam-prep-ai-frontend-1 "the frontend"

log "Building backend and frontend images"
docker compose build --progress=plain backend frontend

log "Running backend test suite inside Docker"
docker compose run --rm --no-deps backend python -m pytest tests/ -q --tb=short

log "Starting local app stack"
docker compose up -d db backend frontend

log "Waiting for API readiness on http://127.0.0.1:${BACKEND_PORT}/ready"
i=0
while [ "$i" -lt 60 ]; do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/ready" >/dev/null; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$i" -ge 60 ]; then
  docker compose logs --tail=120 backend
  printf '\nBackend did not become ready within 60 seconds.\n' >&2
  exit 1
fi

log "Running API smoke test against Docker backend"
docker compose exec -T backend python scripts/e2e_smoke.py

log "Checking frontend is reachable on http://127.0.0.1:${FRONTEND_PORT}"
curl -fsS -I "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null

log "Checking backend CORS allows http://localhost:${FRONTEND_PORT}"
cors_headers="$(curl -fsS -D - -o /dev/null -H "Origin: http://localhost:${FRONTEND_PORT}" "http://127.0.0.1:${BACKEND_PORT}/health")"
printf '%s\n' "$cors_headers" | grep -i "access-control-allow-origin: http://localhost:${FRONTEND_PORT}" >/dev/null

log "Local verification passed"
printf '\nFrontend: http://localhost:%s\nBackend:  http://localhost:%s\nDocs:     http://localhost:%s/docs\n' "$FRONTEND_PORT" "$BACKEND_PORT" "$BACKEND_PORT"
