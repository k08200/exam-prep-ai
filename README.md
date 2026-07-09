# Exam Prep AI

Hyper-personalized AI exam prep. Upload your lecture materials → AI learns your professor's exam style → generates unlimited style-matched mock exams.

## Features
- Upload syllabus, lecture slides, past exams (PDF, PPTX, DOCX, images)
- AI analyzes professor's style using Claude Opus 4.1 with extended thinking
- Generates unlimited mock exams matching your professor's exact style
- Real-time scoring + professor-perspective explanations
- Weakness heatmap tracking your weakest concepts
- Cram mode for pre-exam power studying
- Real-time token usage counter

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key only if you want real Claude output. Local development defaults to deterministic mock AI responses.
- Python 3.10+ and Node.js 20+ if you run backend/frontend directly without Docker.

### Setup
```bash
git clone <repo>
cd exam-prep-ai
cp .env.example .env
# Optional: edit .env and set USE_MOCK_CLAUDE=false plus ANTHROPIC_API_KEY=your-key-here
```

### Run
```bash
docker compose up --build
```

App available at:
- Frontend: http://localhost:3003
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs
- Readiness: http://localhost:8001/ready

If one of those ports is already in use, override the host ports:
```bash
BACKEND_PORT=8011 FRONTEND_PORT=3013 NEXT_PUBLIC_API_URL=http://localhost:8011 docker compose up --build
```

### One-Command Local Verification
To check the full local stack before relying on it for real study work:
```bash
./scripts/local_verify.sh
```

This validates Docker Compose, rebuilds the backend/frontend, runs the backend test suite, starts the local app, runs the API smoke flow, and confirms the frontend is reachable. It keeps your Docker volumes intact.

If verification stops at `Docker is not responding`, open or restart Docker Desktop, wait until it reports that it is running, confirm `docker version` returns normally, then run the script again.

If another app already uses the default local ports, run verification on alternate ports:
```bash
BACKEND_PORT=8011 FRONTEND_PORT=3013 ./scripts/local_verify.sh
```

### Development With Hot Reload
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

The dev override bind-mounts `backend/` and `frontend/` into the containers:
- Backend reloads through `uvicorn --reload`
- Frontend runs `next dev`
- Backend runs `alembic upgrade head` before starting unless `RUN_MIGRATIONS=false`
- Uploaded files still persist in the shared `uploads_data` volume

## Runtime Safety

The backend adds a request ID to every response (`X-Request-ID`), logs request outcomes, caps request setup time with `REQUEST_TIMEOUT_SECONDS`, and rate-limits repeated failed logins with `AUTH_RATE_LIMIT_MAX_FAILURES` over `AUTH_RATE_LIMIT_WINDOW_SECONDS`. AI streams send heartbeat events and fail with a retryable timeout after `AI_STREAM_EVENT_TIMEOUT_SECONDS` without upstream progress. Uploads also validate obvious extension/content-type mismatches before saving files.

## Architecture

```
exam-prep-ai/
├── backend/          # FastAPI Python backend
│   ├── app/
│   │   ├── core/     # Config, security, database
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── schemas/  # Pydantic schemas
│   │   ├── routers/  # API route handlers
│   │   └── services/ # Business logic (Claude API, file parsing)
│   ├── migrations/   # Alembic database migrations
│   └── tests/        # pytest test suite
├── frontend/         # Next.js React frontend
│   └── src/
│       ├── app/      # Next.js App Router pages
│       ├── components/ # Reusable UI components
│       ├── hooks/    # Custom React hooks (useSSE, useAuth)
│       ├── lib/      # API client, utilities
│       └── types/    # TypeScript type definitions
├── docker-compose.yml
├── init.sql          # PostgreSQL initialization
└── .env.example      # Environment variables template
```

## How It Works

1. **Upload**: Add your syllabus + lecture slides + past exams
2. **Analyze**: AI extracts professor's exam patterns using extended thinking (takes 30-60s for deep analysis)
3. **Generate**: Get unlimited mock exams in your professor's exact style
4. **Study**: Take exams, get AI-graded feedback from professor's perspective
5. **Track**: See your weakness heatmap and improve weak concepts

## Claude API Integration

Uses Claude Opus 4.1 with extended thinking:
- **Pattern Analysis**: 30,000 token thinking budget for deep professor style extraction
- **Exam Generation**: 10,000 token thinking budget per question for style verification
- **Grading**: Instant grading with professor-perspective explanations
- All responses stream in real-time via SSE

Note: The `thinking: {type: "adaptive"}` specification uses Claude's extended thinking feature implemented as `{"type": "enabled", "budget_tokens": N}` per the current Anthropic API.

## API Endpoints

### Meta
- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe for DB and upload storage

### Auth
- `POST /auth/register` - Create account
- `POST /auth/login` - Login (returns JWT)
- `GET /auth/me` - Get current user
- `PATCH /auth/me` - Update profile
- `PATCH /auth/me/password` - Change password
- `DELETE /auth/me` - Delete account

### Courses
- `GET /courses` - List your courses
- `POST /courses` - Create course
- `GET /courses/{id}` - Get course

### Materials
- `POST /courses/{id}/materials` - Upload files
- `GET /courses/{id}/materials` - List files
- `POST /courses/{id}/materials/{material_id}/retry` - Retry failed parsing
- `DELETE /courses/{id}/materials/{material_id}` - Delete uploaded file

### Analysis (SSE Streaming)
- `POST /courses/{id}/analysis` - Start professor analysis (streaming)
- `GET /courses/{id}/analysis` - Get saved analysis

### Exams (SSE Streaming)
- `POST /courses/{id}/exams` - Generate exam (streaming)
- `GET /courses/{id}/exams` - List course exams
- `GET /exams` - List recent exams across courses
- `GET /exams/{id}` - Get exam with questions
- `DELETE /exams/{id}` - Delete an exam and its answers
- `POST /exams/{id}/submit` - Submit answers, get results
- `GET /exams/{id}/result` - Re-open saved grading results
- `GET /courses/{id}/heatmap` - Get weakness heatmap

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt
# Set .env variables
uvicorn app.main:app --reload
```

### Run Tests
```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

### Run Local Smoke Test
Start the backend first, then run:
```bash
cd backend
E2E_API_URL=http://127.0.0.1:8000 python scripts/e2e_smoke.py
```

The smoke test covers registration, login, course creation, material upload and retry, analysis streaming, exam generation, submission, and saved result retrieval.

If you are using the root Docker Compose setup, the backend is exposed on port `8001`:
```bash
cd backend
E2E_API_URL=http://127.0.0.1:8001 python scripts/e2e_smoke.py
```

To verify real Claude credentials and model configuration:
```bash
cd backend
USE_MOCK_CLAUDE=false ANTHROPIC_API_KEY=your-key python scripts/claude_smoke.py
```

To run the browser smoke flow, start the backend and frontend first, then run:
```bash
cd frontend
E2E_BASE_URL=http://127.0.0.1:3000 npm run e2e
```

### Database Migrations
```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

`DATABASE_URL` is read from the same environment settings as the app. Docker startup runs `alembic upgrade head` automatically by default. Set `RUN_MIGRATIONS=false` only when another release step already handles migrations.

For legacy local Docker volumes that were originally created with SQLAlchemy `create_all`, the initial migration is intentionally tolerant: it stamps the existing schema path and adds the `materials.processing_error` column if it is missing.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| ENVIRONMENT | Runtime mode (`development` or `production`) | No (default: development) |
| ANTHROPIC_API_KEY | Your Anthropic API key | Only when `USE_MOCK_CLAUDE=false` |
| DATABASE_URL | PostgreSQL connection string | Yes |
| SECRET_KEY | JWT secret (32+ chars) | Yes |
| USE_MOCK_CLAUDE | Use deterministic mock AI responses | No (default in Docker: true) |
| BACKEND_PORT | Host port for Docker backend | No (default: 8001) |
| FRONTEND_PORT | Host port for Docker frontend | No (default: 3003) |
| POSTGRES_PORT | Host port for Docker Postgres | No (default: 5434) |
| RUN_MIGRATIONS | Run Alembic before backend startup | No (default: true) |
| AUTO_CREATE_TABLES | Fallback SQLAlchemy table creation | No (default in Docker: false) |
| CORS_ORIGINS | Comma-separated frontend origins allowed by the API | No (local defaults) |
| MATERIAL_PROCESSING_STALE_MINUTES | Mark abandoned material parsing jobs failed after this many minutes | No (default: 30) |
| MAX_UPLOAD_FILES | Maximum number of files per upload request | No (default: 10) |
| CLAUDE_MODEL | Claude model ID | No (default: claude-opus-4-1-20250805) |
| THINKING_BUDGET_ANALYSIS | Thinking tokens for analysis | No (default: 30000) |
| THINKING_BUDGET_GENERATION | Thinking tokens for generation | No (default: 10000) |
