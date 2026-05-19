import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, courses, materials, analysis, exams


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    # Create upload directory
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)

    if settings.AUTO_CREATE_TABLES:
        await init_db()

    await materials.recover_stale_processing_materials()

    yield

    # Shutdown: nothing to clean up for now


app = FastAPI(
    title="Exam Prep AI",
    description=(
        "Hyper-Personalized AI Exam Prep — upload lecture materials, "
        "let Claude analyse your professor's exam style, and get style-matched mock exams."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Flutter/Tauri frontend running locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "tauri://localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(materials.router)
app.include_router(analysis.router)
app.include_router(exams.router)


@app.get("/health", tags=["meta"])
async def health_check() -> dict:
    """Simple liveness probe."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "ai_mode": "mock" if settings.USE_MOCK_CLAUDE else "claude",
        "claude_configured": bool(settings.ANTHROPIC_API_KEY),
    }


@app.get("/", tags=["meta"])
async def root() -> dict:
    """API root — returns basic info."""
    return {
        "name": "Exam Prep AI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
