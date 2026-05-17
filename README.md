# Exam Prep AI

Hyper-personalized AI exam prep. Upload your lecture materials → AI learns your professor's exam style → generates unlimited style-matched mock exams.

## Features
- Upload syllabus, lecture slides, past exams (PDF, PPT, DOCX, images)
- AI analyzes professor's style using Claude claude-opus-4-7 with extended thinking
- Generates unlimited mock exams matching your professor's exact style
- Real-time scoring + professor-perspective explanations
- Weakness heatmap tracking your weakest concepts
- Cram mode for pre-exam power studying
- Real-time token usage counter

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key

### Setup
```bash
git clone <repo>
cd exam-prep-ai
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your-key-here
```

### Run
```bash
docker-compose up --build
```

App available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

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

Uses Claude claude-opus-4-7 with extended thinking:
- **Pattern Analysis**: 30,000 token thinking budget for deep professor style extraction
- **Exam Generation**: 10,000 token thinking budget per question for style verification
- **Grading**: Instant grading with professor-perspective explanations
- All responses stream in real-time via SSE

Note: The `thinking: {type: "adaptive"}` specification uses Claude's extended thinking feature implemented as `{"type": "enabled", "budget_tokens": N}` per the current Anthropic API.

## API Endpoints

### Auth
- `POST /auth/register` - Create account
- `POST /auth/login` - Login (returns JWT)
- `GET /auth/me` - Get current user

### Courses
- `GET /courses` - List your courses
- `POST /courses` - Create course
- `GET /courses/{id}` - Get course

### Materials
- `POST /courses/{id}/materials` - Upload files
- `GET /courses/{id}/materials` - List files

### Analysis (SSE Streaming)
- `POST /courses/{id}/analysis` - Start professor analysis (streaming)
- `GET /courses/{id}/analysis` - Get saved analysis

### Exams (SSE Streaming)
- `POST /courses/{id}/exams` - Generate exam (streaming)
- `GET /exams/{id}` - Get exam with questions
- `POST /exams/{id}/submit` - Submit answers, get results
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

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| ANTHROPIC_API_KEY | Your Anthropic API key | Yes |
| DATABASE_URL | PostgreSQL connection string | Yes |
| SECRET_KEY | JWT secret (32+ chars) | Yes |
| CLAUDE_MODEL | Claude model ID | No (default: claude-opus-4-7) |
| THINKING_BUDGET_ANALYSIS | Thinking tokens for analysis | No (default: 30000) |
| THINKING_BUDGET_GENERATION | Thinking tokens for generation | No (default: 10000) |
