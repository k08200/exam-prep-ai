# Deployment Checklist

## Runtime

- Run PostgreSQL 16 or compatible.
- Set `ENVIRONMENT=production` so the backend fails fast on unsafe runtime settings.
- Set `DATABASE_URL` to an async SQLAlchemy URL, for example `postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB`.
- Set a production `SECRET_KEY` with at least 32 random characters.
- Set `RUN_MIGRATIONS=true` unless the platform has a separate migration release step.
- Set `AUTO_CREATE_TABLES=false` in production.
- Keep `EXAM_GENERATION_STALE_MINUTES` long enough for the slowest expected Claude generation so an active stream is not reclaimed.
- Keep `ANALYSIS_RUN_STALE_MINUTES` longer than the slowest expected analysis stream so an active run is not reclaimed while still running.
- Mount persistent storage for `UPLOAD_DIR`.
- Set `MAX_USER_STORAGE_BYTES` to a per-user limit appropriate for the disk available to your users.
- Set `MAX_DAILY_AI_ANALYSES`, `MAX_DAILY_AI_GENERATED_QUESTIONS`, and `MAX_DAILY_AI_GRADES` to a budget that matches the configured Claude model and account plan. Limits reset at midnight UTC and are reserved before provider work starts.
- Tune `REQUEST_TIMEOUT_SECONDS`, `AI_STREAM_HEARTBEAT_SECONDS`, and `AI_STREAM_EVENT_TIMEOUT_SECONDS` for your platform timeout limits.

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
CLAUDE_MODEL=claude-opus-4-8
CLAUDE_THINKING_EFFORT=high
MAX_DAILY_AI_ANALYSES=10
MAX_DAILY_AI_GENERATED_QUESTIONS=200
MAX_DAILY_AI_GRADES=300
```

The backend now fails fast if `USE_MOCK_CLAUDE=false` and `ANTHROPIC_API_KEY` is empty. Confirm the active mode with:

```bash
curl https://your-api.example.com/health
```

Expected production fields:

```json
{
  "status": "ok",
  "ai": "ok",
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
- Set `CORS_ORIGINS` to the deployed frontend origin, for example `https://app.example.com`.
- Run `npm audit --audit-level=high` and `npm run build` before deployment.

## Smoke Test

After deployment, run the API smoke test from a trusted environment:

```bash
cd backend
E2E_API_URL=https://your-api.example.com python scripts/e2e_smoke.py
```

This checks auth, course creation, material parsing, failed material retry, analysis streaming, exam generation, submission, and persisted result retrieval.

Verify real Claude credentials and model configuration before disabling mock mode:

```bash
cd backend
USE_MOCK_CLAUDE=false ANTHROPIC_API_KEY=your_anthropic_key python scripts/claude_smoke.py
```

For browser-level validation, run the frontend against the deployed API and execute:

```bash
cd frontend
E2E_BASE_URL=https://your-frontend.example.com npm run e2e
```

## Backups and User Data

For a local Docker installation, create a complete database-and-upload archive with:

```bash
./scripts/backup_local.sh
```

Store the resulting `backups/*.tar.gz` archive somewhere separate from the machine. To replace a local installation with that backup, use the explicit destructive restore command:

```bash
./scripts/restore_local.sh backups/exam-prep-ai-YYYYMMDDTHHMMSSZ.tar.gz --force
```

Individual users can export their own study data from Settings. The export deliberately excludes password hashes, active sessions, and server secrets.

## Health Gates

Before routing traffic:

- `/health` returns `status: ok`.
- `/ready` returns `status: ready`, `database: ok`, and `upload_dir: ok`.
- `alembic upgrade head` has completed.
- The `0005_analysis_runs` migration is applied so daily AI limits, shared analysis locking, concurrent draft-generation protection, and password session invalidation work correctly.
- Frontend build points to the production API URL.
- `USE_MOCK_CLAUDE` is false only when `ANTHROPIC_API_KEY` is configured.
- Upload storage is persistent across restarts.
- `MAX_UPLOAD_FILES` and `MAX_FILE_SIZE` match the frontend limits.
