import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("USE_MOCK_CLAUDE", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("UPLOAD_DIR", "/tmp/test-uploads")

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
async def db_engine():
    """Create an in-memory SQLite engine and initialise all tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # Import all models so metadata is populated
        import app.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a test session that rolls back after each test."""
    TestSession = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the FastAPI app with the test DB session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register + login a test user and return auth headers."""
    await client.post(
        "/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "testpassword123",
            "full_name": "Test User",
        },
    )
    login_resp = await client.post(
        "/auth/login",
        data={
            "username": "testuser@example.com",
            "password": "testpassword123",
        },
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_course(client: AsyncClient, auth_headers: dict) -> dict:
    """Create a test course and return its JSON response."""
    resp = await client.post(
        "/courses",
        json={
            "name": "Introduction to Machine Learning",
            "description": "Core ML concepts",
            "professor_name": "Dr. Smith",
            "subject": "Computer Science",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()
