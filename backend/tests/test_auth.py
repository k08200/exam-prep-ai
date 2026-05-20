"""
TDD tests for authentication endpoints.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient) -> None:
    """A new user can register with a valid email and password."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "securepass123",
            "full_name": "New User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient) -> None:
    """Registering with an already-used email returns 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "password": "securepass123",
    }
    resp1 = await client.post("/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_email_is_case_insensitive(client: AsyncClient) -> None:
    """Email addresses are canonicalized so case variants cannot create duplicates."""
    resp1 = await client.post(
        "/auth/register",
        json={"email": "MixedCase@example.com", "password": "securepass123"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["email"] == "mixedcase@example.com"

    resp2 = await client.post(
        "/auth/register",
        json={"email": "mixedcase@EXAMPLE.com", "password": "securepass123"},
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_login_email_is_case_insensitive(client: AsyncClient) -> None:
    """A user can log in with email casing different from registration."""
    await client.post(
        "/auth/register",
        json={"email": "login-case@example.com", "password": "securepass123"},
    )

    resp = await client.post(
        "/auth/login",
        data={"username": "LOGIN-CASE@EXAMPLE.COM", "password": "securepass123"},
    )

    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_register_invalid_email_fails(client: AsyncClient) -> None:
    """Registering with a malformed email returns 422 Unprocessable Entity."""
    resp = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "securepass123"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_short_fails(client: AsyncClient) -> None:
    """Password shorter than 8 characters is rejected at schema level."""
    resp = await client.post(
        "/auth/register",
        json={"email": "shortpw@example.com", "password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success_returns_token(client: AsyncClient) -> None:
    """A registered user can log in and receive a JWT token."""
    await client.post(
        "/auth/register",
        json={"email": "logintest@example.com", "password": "securepass123"},
    )
    resp = await client.post(
        "/auth/login",
        data={"username": "logintest@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 10


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client: AsyncClient) -> None:
    """Logging in with the wrong password returns 401 Unauthorized."""
    await client.post(
        "/auth/register",
        json={"email": "wrongpw@example.com", "password": "correctpass123"},
    )
    resp = await client.post(
        "/auth/login",
        data={"username": "wrongpw@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_fails(client: AsyncClient) -> None:
    """Logging in with a non-existent email returns 401 Unauthorized."""
    resp = await client.post(
        "/auth/login",
        data={"username": "ghost@example.com", "password": "anypassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_after_repeated_failures(
    client: AsyncClient,
    monkeypatch,
) -> None:
    """Repeated failed logins for the same email are temporarily rate-limited."""
    from app.core.config import settings
    from app.routers.auth import _clear_failed_logins

    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_MAX_FAILURES", 2)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)
    _clear_failed_logins()

    await client.post(
        "/auth/register",
        json={"email": "ratelimit@example.com", "password": "securepass123"},
    )

    for _ in range(2):
        resp = await client.post(
            "/auth/login",
            data={"username": "ratelimit@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    limited = await client.post(
        "/auth/login",
        data={"username": "ratelimit@example.com", "password": "wrongpassword"},
    )

    assert limited.status_code == 429
    assert "too many" in limited.json()["detail"].lower()
    _clear_failed_logins()


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_headers: dict) -> None:
    """An authenticated user can retrieve their own profile."""
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "testuser@example.com"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Accessing /auth/me without a token returns 401 Unauthorized."""
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token_returns_401(client: AsyncClient) -> None:
    """An invalid or tampered JWT returns 401 Unauthorized."""
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer this.is.invalid"},
    )
    assert resp.status_code == 401
