#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" != "false" ]; then
  alembic upgrade head
fi

if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
