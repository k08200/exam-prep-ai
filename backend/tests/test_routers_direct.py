"""
Direct unit tests for router functions (bypassing HTTP/ASGI).
These ensure coverage is tracked for async route handlers.
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import UserCreate
from app.schemas.course import CourseCreate, CourseUpdate


# ── auth router ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_direct(db_session: AsyncSession) -> None:
    """Direct call to register() creates a user and returns UserResponse."""
    from app.routers.auth import register

    user_in = UserCreate(email="direct1@example.com", password="password123")
    result = await register(user_in, db=db_session)

    assert result.email == "direct1@example.com"
    assert result.is_active is True
    assert "id" in result.model_dump()


@pytest.mark.asyncio
async def test_register_direct_duplicate_raises_409(db_session: AsyncSession) -> None:
    """register() raises 409 when email is already taken."""
    from app.routers.auth import register

    user_in = UserCreate(email="dup@example.com", password="password123")
    await register(user_in, db=db_session)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await register(user_in, db=db_session)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_login_direct_success(db_session: AsyncSession) -> None:
    """Direct call to login() returns a JWT token for valid credentials."""
    from fastapi.security import OAuth2PasswordRequestForm
    from app.routers.auth import register, login
    from app.schemas.auth import UserCreate

    # Register first
    await register(UserCreate(email="logindir@example.com", password="pass12345"), db=db_session)
    await db_session.flush()

    # Create form data mock
    form = OAuth2PasswordRequestForm(username="logindir@example.com", password="pass12345", scope="")
    token = await login(form_data=form, db=db_session)

    assert token.token_type == "bearer"
    assert len(token.access_token) > 10


@pytest.mark.asyncio
async def test_login_direct_wrong_password(db_session: AsyncSession) -> None:
    """login() raises 401 for wrong password."""
    from fastapi.security import OAuth2PasswordRequestForm
    from app.routers.auth import register, login

    await register(UserCreate(email="badpw@example.com", password="correctpass"), db=db_session)
    await db_session.flush()

    form = OAuth2PasswordRequestForm(username="badpw@example.com", password="wrongpass", scope="")
    with pytest.raises(HTTPException) as exc_info:
        await login(form_data=form, db=db_session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_direct_nonexistent_user(db_session: AsyncSession) -> None:
    """login() raises 401 for unknown user."""
    from fastapi.security import OAuth2PasswordRequestForm
    from app.routers.auth import login

    form = OAuth2PasswordRequestForm(username="ghost@example.com", password="anypass", scope="")
    with pytest.raises(HTTPException) as exc_info:
        await login(form_data=form, db=db_session)
    assert exc_info.value.status_code == 401


# ── courses router ─────────────────────────────────────────────────────────


@pytest.fixture
async def direct_user(db_session: AsyncSession):
    """Create and return a test user directly in DB."""
    from app.routers.auth import register

    result = await register(
        UserCreate(email="courseuser@example.com", password="password123"),
        db=db_session,
    )
    await db_session.flush()

    from sqlalchemy import select
    from app.models.user import User
    row = await db_session.execute(select(User).where(User.email == "courseuser@example.com"))
    return row.scalar_one()


@pytest.mark.asyncio
async def test_create_course_direct(db_session: AsyncSession, direct_user) -> None:
    """Direct call to create_course() returns a CourseResponse."""
    from app.routers.courses import create_course

    course_in = CourseCreate(name="Direct Course", professor_name="Dr. Direct")
    result = await create_course(course_in=course_in, current_user=direct_user, db=db_session)

    assert result.name == "Direct Course"
    assert result.professor_name == "Dr. Direct"
    assert result.material_count == 0
    assert result.has_analysis is False


@pytest.mark.asyncio
async def test_list_courses_direct(db_session: AsyncSession, direct_user) -> None:
    """Direct call to list_courses() returns the user's courses."""
    from app.routers.courses import create_course, list_courses

    await create_course(CourseCreate(name="Course X"), current_user=direct_user, db=db_session)
    await create_course(CourseCreate(name="Course Y"), current_user=direct_user, db=db_session)
    await db_session.flush()

    courses = await list_courses(current_user=direct_user, db=db_session)
    names = [c.name for c in courses]
    assert "Course X" in names
    assert "Course Y" in names


@pytest.mark.asyncio
async def test_get_course_direct(db_session: AsyncSession, direct_user) -> None:
    """Direct call to get_course() returns the correct course."""
    from app.routers.courses import create_course, get_course

    created = await create_course(CourseCreate(name="Get Me"), current_user=direct_user, db=db_session)
    await db_session.flush()

    fetched = await get_course(course_id=created.id, current_user=direct_user, db=db_session)
    assert fetched.id == created.id
    assert fetched.name == "Get Me"


@pytest.mark.asyncio
async def test_get_course_direct_not_found(db_session: AsyncSession, direct_user) -> None:
    """get_course() raises 404 for a non-existent course."""
    from app.routers.courses import get_course

    with pytest.raises(HTTPException) as exc_info:
        await get_course(course_id=uuid.uuid4(), current_user=direct_user, db=db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_course_direct(db_session: AsyncSession, direct_user) -> None:
    """Direct call to update_course() updates course fields."""
    from app.routers.courses import create_course, update_course

    created = await create_course(CourseCreate(name="Old"), current_user=direct_user, db=db_session)
    await db_session.flush()

    updated = await update_course(
        course_id=created.id,
        course_update=CourseUpdate(name="New", professor_name="Updated Prof"),
        current_user=direct_user,
        db=db_session,
    )
    assert updated.name == "New"
    assert updated.professor_name == "Updated Prof"


@pytest.mark.asyncio
async def test_update_course_direct_not_found(db_session: AsyncSession, direct_user) -> None:
    """update_course() raises 404 for a non-existent course."""
    from app.routers.courses import update_course

    with pytest.raises(HTTPException) as exc_info:
        await update_course(
            course_id=uuid.uuid4(),
            course_update=CourseUpdate(name="Ghost"),
            current_user=direct_user,
            db=db_session,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_course_direct(db_session: AsyncSession, direct_user) -> None:
    """Direct call to delete_course() removes the record."""
    from app.routers.courses import create_course, delete_course, get_course

    created = await create_course(CourseCreate(name="Delete Me"), current_user=direct_user, db=db_session)
    await db_session.flush()

    await delete_course(course_id=created.id, current_user=direct_user, db=db_session)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await get_course(course_id=created.id, current_user=direct_user, db=db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_course_direct_not_found(db_session: AsyncSession, direct_user) -> None:
    """delete_course() raises 404 for a non-existent course."""
    from app.routers.courses import delete_course

    with pytest.raises(HTTPException) as exc_info:
        await delete_course(course_id=uuid.uuid4(), current_user=direct_user, db=db_session)
    assert exc_info.value.status_code == 404


# ── auth update/delete ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_me_direct(db_session: AsyncSession) -> None:
    """update_me() updates full_name and returns updated UserResponse."""
    from app.routers.auth import register, update_me
    from app.schemas.auth import UserUpdate

    user_resp = await register(UserCreate(email="updateme@example.com", password="password123"), db=db_session)
    await db_session.flush()

    from sqlalchemy import select
    from app.models.user import User
    row = await db_session.execute(select(User).where(User.email == "updateme@example.com"))
    user = row.scalar_one()

    result = await update_me(UserUpdate(full_name="New Name"), current_user=user, db=db_session)
    assert result.full_name == "New Name"
    assert result.email == "updateme@example.com"


@pytest.mark.asyncio
async def test_update_me_direct_no_change(db_session: AsyncSession) -> None:
    """update_me() with full_name=None leaves the field unchanged."""
    from app.routers.auth import register, update_me
    from app.schemas.auth import UserUpdate

    await register(UserCreate(email="noop@example.com", password="password123", full_name="Original"), db=db_session)
    await db_session.flush()

    from sqlalchemy import select
    from app.models.user import User
    row = await db_session.execute(select(User).where(User.email == "noop@example.com"))
    user = row.scalar_one()

    result = await update_me(UserUpdate(full_name=None), current_user=user, db=db_session)
    assert result.full_name == "Original"


@pytest.mark.asyncio
async def test_change_password_direct_success(db_session: AsyncSession) -> None:
    """change_password() succeeds with correct current password."""
    from app.routers.auth import register, change_password
    from app.schemas.auth import PasswordChange

    await register(UserCreate(email="chpw@example.com", password="oldpassword"), db=db_session)
    await db_session.flush()

    from sqlalchemy import select
    from app.models.user import User
    row = await db_session.execute(select(User).where(User.email == "chpw@example.com"))
    user = row.scalar_one()

    # Should not raise
    await change_password(PasswordChange(current_password="oldpassword", new_password="newpassword123"), current_user=user, db=db_session)


@pytest.mark.asyncio
async def test_change_password_direct_wrong_current(db_session: AsyncSession) -> None:
    """change_password() raises 401 for incorrect current password."""
    from app.routers.auth import register, change_password
    from app.schemas.auth import PasswordChange

    await register(UserCreate(email="chpw2@example.com", password="correctpass"), db=db_session)
    await db_session.flush()

    from sqlalchemy import select
    from app.models.user import User
    row = await db_session.execute(select(User).where(User.email == "chpw2@example.com"))
    user = row.scalar_one()

    with pytest.raises(HTTPException) as exc_info:
        await change_password(PasswordChange(current_password="wrongpass", new_password="newpassword123"), current_user=user, db=db_session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_delete_me_direct(db_session: AsyncSession) -> None:
    """delete_me() removes the user from the database."""
    from app.routers.auth import register, delete_me

    await register(UserCreate(email="deleteme@example.com", password="password123"), db=db_session)
    await db_session.flush()

    from sqlalchemy import select
    from app.models.user import User
    row = await db_session.execute(select(User).where(User.email == "deleteme@example.com"))
    user = row.scalar_one()

    await delete_me(current_user=user, db=db_session)
    await db_session.flush()

    row2 = await db_session.execute(select(User).where(User.email == "deleteme@example.com"))
    assert row2.scalar_one_or_none() is None


# ── exams router — list all ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_all_exams_direct_empty(db_session: AsyncSession, direct_user) -> None:
    """list_all_exams() returns empty list when user has no exams."""
    from app.routers.exams import list_all_exams

    result = await list_all_exams(current_user=direct_user, db=db_session, limit=20)
    assert result == []
