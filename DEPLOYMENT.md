# Deployment Checklist

## Runtime

- Run PostgreSQL 16 or compatible.
- Set `DATABASE_URL` to an async SQLAlchemy URL, for example `postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB`.
- Set a production `SECRET_KEY` with at least 32 random characters.
- Set `RUN_MIGRATIONS=true` unless the platform has a separate migration release step.
- Set `AUTO_CREATE_TABLES=false` in production.
- Mount persistent storage for `UPLOAD_DIR`.

## AI Mode

Development can run with deterministic mock output:

```bash
USE_MOCK_CLAUDE=true
ANTHROPIC_API_KEY=
```

Production Claude mode must be explicit:

```bash
USE_MOCK_CLAUDE=false
ANTHROPIC_API_KEY=your_anthropic_key
CLAUDE_MODEL=claude-opus-4-1-20250805
```

The backend now fails fast if `USE_MOCK_CLAUDE=false` and `ANTHROPIC_API_KEY` is empty. Confirm the active mode with:

```bash
curl https://your-api.example.com/health
```

Expected production fields:

```json
{
  "status": "ok",
  "ai_mode": "claude",
  "claude_configured": true
}
```

## Migrations

Docker startup runs:

```bash
alembic upgrade head
```

The initial migration tolerates legacy local databases that were created before Alembic was added. New production databases should still be migrated normally from an empty schema.

## Frontend

- Build with `NEXT_PUBLIC_API_URL` pointing at the deployed backend URL.
- Keep the frontend origin in the backend CORS allowlist.
- Run `npm audit --audit-level=high` and `npm run build` before deployment.

## Smoke Test

After deployment, run the API smoke test from a trusted environment:

```bash
cd backend
E2E_API_URL=https://your-api.example.com python scripts/e2e_smoke.py
```

This checks auth, course creation, material parsing, failed material retry, analysis streaming, exam generation, submission, and persisted result retrieval.

## Health Gates

Before routing traffic:

- `/health` returns `status: ok`.
- `alembic upgrade head` has completed.
- Frontend build points to the production API URL.
- `USE_MOCK_CLAUDE` is false only when `ANTHROPIC_API_KEY` is configured.
- Upload storage is persistent across restarts.
