import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, init_db
from app.core.middleware import request_context_middleware
from app.routers import auth, courses, materials, analysis, exams


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    settings.validate_runtime_settings()

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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_context_middleware)

# Routers
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(materials.router)
app.include_router(analysis.router)
app.include_router(exams.router)


@app.get("/health", tags=["meta"])
async def health_check() -> dict:
    """Simple liveness probe."""
    ai_ready = settings.USE_MOCK_CLAUDE or bool(settings.ANTHROPIC_API_KEY)
    return {
        "status": "ok",
        "version": "1.0.0",
        "ai": "ok" if ai_ready else "not_configured",
        "ai_mode": "mock" if settings.USE_MOCK_CLAUDE else "claude",
        "claude_configured": bool(settings.ANTHROPIC_API_KEY),
    }


@app.get("/ready", tags=["meta"])
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe for dependencies required to serve real traffic."""
    await db.execute(text("SELECT 1"))
    upload_path = Path(settings.UPLOAD_DIR)
    upload_ready = upload_path.exists() and upload_path.is_dir() and os.access(upload_path, os.W_OK)
    ai_ready = settings.USE_MOCK_CLAUDE or bool(settings.ANTHROPIC_API_KEY)

    return {
        "status": "ready" if upload_ready and ai_ready else "not_ready",
        "database": "ok",
        "upload_dir": "ok" if upload_ready else "not_writable",
        "ai": "ok" if ai_ready else "not_configured",
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
