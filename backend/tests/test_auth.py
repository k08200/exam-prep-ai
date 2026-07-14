"""
TDD tests for authentication endpoints.
"""
import json

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


@pytest.mark.asyncio
async def test_export_my_data_contains_only_the_current_users_study_data(
    client: AsyncClient,
    db_session,
) -> None:
    """A user can export their own study archive without secrets or other users' data."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.analysis import ProfessorAnalysis
    from app.models.exam import ConceptTracking, Exam, ExamQuestion, StudentResponse
    from app.models.material import Material
    from app.models.user import User
    from app.routers.auth import export_my_data

    owner_email = "export-owner@example.com"
    await client.post(
        "/auth/register",
        json={"email": owner_email, "password": "securepass123", "full_name": "Export Owner"},
    )
    owner_login = await client.post(
        "/auth/login",
        data={"username": owner_email, "password": "securepass123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    own_course = await client.post(
        "/courses",
        json={"name": "Exported Course", "subject": "Statistics"},
        headers=owner_headers,
    )
    assert own_course.status_code == 201

    owner_result = await db_session.execute(select(User).where(User.email == owner_email))
    owner = owner_result.scalar_one()
    course_id = UUID(own_course.json()["id"])
    material = Material(
        course_id=course_id,
        filename="exported.pdf",
        original_filename="exported.pdf",
        file_type="pdf",
        file_path="/tmp/exported.pdf",
        file_size=42,
        extracted_text="Exported lecture material",
        page_count=1,
        processing_status="completed",
    )
    analysis = ProfessorAnalysis(
        course_id=course_id,
        top_concepts=[{"concept": "Bayes", "frequency": 2, "importance_score": 0.9, "description": "Core"}],
        question_types={"multiple_choice": 100, "essay": 0, "calculation": 0, "true_false": 0},
        topic_distribution={"Bayesian inference": 100},
        professor_terms=[],
        exam_patterns={"emphasis": "proof"},
        raw_analysis="Saved analysis",
        thinking_tokens_used=10,
        total_tokens_used=20,
    )
    exam = Exam(
        course_id=course_id,
        user_id=owner.id,
        title="Exported Midterm",
        mode="standard",
        question_count=1,
        status="completed",
        score=100,
        total_tokens_used=30,
    )
    db_session.add_all([material, analysis, exam])
    await db_session.flush()
    question = ExamQuestion(
        exam_id=exam.id,
        question_number=1,
        question_text="What is Bayes' theorem?",
        question_type="essay",
        choices=None,
        correct_answer="A theorem for conditional probability.",
        explanation="Use conditional probability.",
        concepts=["Bayes"],
        difficulty="medium",
        tokens_used=30,
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add_all(
        [
            StudentResponse(
                exam_id=exam.id,
                question_id=question.id,
                user_id=owner.id,
                student_answer="Conditional probability",
                is_correct=True,
                score=1,
                ai_feedback="Correct.",
            ),
            ConceptTracking(
                user_id=owner.id,
                course_id=course_id,
                concept="Bayes",
                attempts=1,
                correct_count=1,
                incorrect_count=0,
                weakness_score=0,
            ),
        ]
    )
    await db_session.commit()

    await client.post(
        "/auth/register",
        json={"email": "export-other@example.com", "password": "securepass123"},
    )
    other_login = await client.post(
        "/auth/login",
        data={"username": "export-other@example.com", "password": "securepass123"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    other_course = await client.post(
        "/courses",
        json={"name": "Private Other Course"},
        headers=other_headers,
    )
    assert other_course.status_code == 201

    response = await client.get("/auth/me/export", headers=owner_headers)
    direct_response = await export_my_data(current_user=owner, db=db_session)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    exported = response.json()
    assert exported["format"] == "exam-prep-ai-user-export"
    assert exported["schema_version"] == 1
    assert exported["user"]["email"] == owner_email
    assert "Exported Course" in [course["name"] for course in exported["courses"]]
    assert "Private Other Course" not in [course["name"] for course in exported["courses"]]
    exported_course = next(course for course in exported["courses"] if course["name"] == "Exported Course")
    assert exported_course["materials"][0]["extracted_text"] == "Exported lecture material"
    assert exported_course["analysis"]["top_concepts"][0]["concept"] == "Bayes"
    assert exported_course["exams"][0]["questions"][0]["correct_answer"].startswith("A theorem")
    assert exported_course["exams"][0]["responses"][0]["is_correct"] is True
    assert exported_course["concept_tracking"][0]["attempts"] == 1
    assert "hashed_password" not in response.text

    direct_export = json.loads(direct_response.body)
    assert direct_export["user"]["email"] == owner_email
