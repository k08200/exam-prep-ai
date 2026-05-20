"""
TDD tests for courses CRUD endpoints.
"""
import pytest
from httpx import AsyncClient
from pathlib import Path
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_create_course_success(client: AsyncClient, auth_headers: dict) -> None:
    """POST /courses creates a course and returns 201."""
    resp = await client.post(
        "/courses",
        json={
            "name": "Advanced Algorithms",
            "description": "Graph theory and NP problems",
            "professor_name": "Dr. Knuth",
            "subject": "Computer Science",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Advanced Algorithms"
    assert data["professor_name"] == "Dr. Knuth"
    assert data["subject"] == "Computer Science"
    assert data["material_count"] == 0
    assert data["has_analysis"] is False
    assert "id" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_create_course_minimal(client: AsyncClient, auth_headers: dict) -> None:
    """POST /courses works with just a name (all other fields optional)."""
    resp = await client.post(
        "/courses",
        json={"name": "Minimal Course"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Minimal Course"
    assert data["professor_name"] is None
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_course_requires_auth(client: AsyncClient) -> None:
    """POST /courses without a token returns 401."""
    resp = await client.post("/courses", json={"name": "Unauthorized"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_courses_returns_only_own(client: AsyncClient, auth_headers: dict) -> None:
    """GET /courses returns only courses belonging to the authenticated user."""
    await client.post("/courses", json={"name": "My Course A"}, headers=auth_headers)
    await client.post("/courses", json={"name": "My Course B"}, headers=auth_headers)

    # Second user creates their own course
    await client.post(
        "/auth/register",
        json={"email": "other_course_user@example.com", "password": "password123"},
    )
    login_resp = await client.post(
        "/auth/login",
        data={"username": "other_course_user@example.com", "password": "password123"},
    )
    other_token = login_resp.json()["access_token"]
    await client.post(
        "/courses",
        json={"name": "Other User Course"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    resp = await client.get("/courses", headers=auth_headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "My Course A" in names
    assert "My Course B" in names
    assert "Other User Course" not in names


@pytest.mark.asyncio
async def test_get_course_by_id(client: AsyncClient, auth_headers: dict) -> None:
    """GET /courses/{id} returns the specific course."""
    create_resp = await client.post(
        "/courses",
        json={"name": "Specific Course", "professor_name": "Dr. Test"},
        headers=auth_headers,
    )
    course_id = create_resp.json()["id"]

    resp = await client.get(f"/courses/{course_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == course_id
    assert data["name"] == "Specific Course"
    assert data["professor_name"] == "Dr. Test"


@pytest.mark.asyncio
async def test_get_course_includes_material_status_counts(
    client: AsyncClient,
    auth_headers: dict,
    test_course: dict,
    db_session,
) -> None:
    """Course responses expose material counts by processing state."""
    import uuid
    from app.models.material import (
        Material,
        PROCESSING_STATUS_COMPLETED,
        PROCESSING_STATUS_FAILED,
        PROCESSING_STATUS_PENDING,
    )

    course_id = uuid.UUID(test_course["id"])
    db_session.add_all(
        [
            Material(
                course_id=course_id,
                filename="ready.pdf",
                original_filename="ready.pdf",
                file_type="pdf",
                file_path="/tmp/ready.pdf",
                file_size=100,
                processing_status=PROCESSING_STATUS_COMPLETED,
            ),
            Material(
                course_id=course_id,
                filename="pending.pdf",
                original_filename="pending.pdf",
                file_type="pdf",
                file_path="/tmp/pending.pdf",
                file_size=100,
                processing_status=PROCESSING_STATUS_PENDING,
            ),
            Material(
                course_id=course_id,
                filename="failed.pdf",
                original_filename="failed.pdf",
                file_type="pdf",
                file_path="/tmp/failed.pdf",
                file_size=100,
                processing_status=PROCESSING_STATUS_FAILED,
            ),
        ]
    )
    await db_session.flush()

    resp = await client.get(f"/courses/{course_id}", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["material_count"] == 3
    assert data["completed_material_count"] == 1
    assert data["processing_material_count"] == 1
    assert data["failed_material_count"] == 1


@pytest.mark.asyncio
async def test_get_course_not_found_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """GET /courses/{id} with a non-existent UUID returns 404."""
    import uuid
    resp = await client.get(f"/courses/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_other_user_course_returns_403(client: AsyncClient, auth_headers: dict) -> None:
    """GET /courses/{id} for another user's course returns 403."""
    await client.post(
        "/auth/register",
        json={"email": "owner_course@example.com", "password": "password123"},
    )
    login_resp = await client.post(
        "/auth/login",
        data={"username": "owner_course@example.com", "password": "password123"},
    )
    other_token = login_resp.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    create_resp = await client.post(
        "/courses", json={"name": "Owner's Private Course"}, headers=other_headers
    )
    course_id = create_resp.json()["id"]

    resp = await client.get(f"/courses/{course_id}", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_course(client: AsyncClient, auth_headers: dict) -> None:
    """PUT /courses/{id} updates course fields."""
    create_resp = await client.post(
        "/courses",
        json={"name": "Old Name", "professor_name": "Old Prof"},
        headers=auth_headers,
    )
    course_id = create_resp.json()["id"]

    resp = await client.put(
        f"/courses/{course_id}",
        json={"name": "New Name", "professor_name": "New Prof"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["professor_name"] == "New Prof"


@pytest.mark.asyncio
async def test_update_course_partial(client: AsyncClient, auth_headers: dict) -> None:
    """PUT /courses/{id} with only some fields updates just those fields."""
    create_resp = await client.post(
        "/courses",
        json={"name": "Original", "professor_name": "Dr. Original"},
        headers=auth_headers,
    )
    course_id = create_resp.json()["id"]

    resp = await client.put(
        f"/courses/{course_id}",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["professor_name"] == "Dr. Original"


@pytest.mark.asyncio
async def test_update_nonexistent_course_returns_404(
    client: AsyncClient, auth_headers: dict
) -> None:
    """PUT /courses/{id} with a bad UUID returns 404."""
    import uuid
    resp = await client.put(
        f"/courses/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_course(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /courses/{id} removes the course."""
    create_resp = await client.post(
        "/courses", json={"name": "To Delete"}, headers=auth_headers
    )
    course_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/courses/{course_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/courses/{course_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_course_removes_uploaded_files(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Deleting a course removes files owned by that course from disk."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    create_resp = await client.post(
        "/courses", json={"name": "Delete Files"}, headers=auth_headers
    )
    course_id = create_resp.json()["id"]

    with patch("app.routers.materials._parse_and_update", new=AsyncMock()):
        upload_resp = await client.post(
            f"/courses/{course_id}/materials",
            files={"files": ("course_delete.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
            headers=auth_headers,
        )

    assert upload_resp.status_code == 201
    uploaded_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(uploaded_files) == 1
    assert uploaded_files[0].exists()

    del_resp = await client.delete(f"/courses/{course_id}", headers=auth_headers)

    assert del_resp.status_code == 204
    assert not uploaded_files[0].exists()


@pytest.mark.asyncio
async def test_delete_other_user_course_returns_403(
    client: AsyncClient, auth_headers: dict
) -> None:
    """DELETE /courses/{id} for another user's course returns 403."""
    await client.post(
        "/auth/register",
        json={"email": "del_owner@example.com", "password": "password123"},
    )
    login_resp = await client.post(
        "/auth/login",
        data={"username": "del_owner@example.com", "password": "password123"},
    )
    other_token = login_resp.json()["access_token"]

    create_resp = await client.post(
        "/courses",
        json={"name": "Cannot Delete Me"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    course_id = create_resp.json()["id"]

    resp = await client.delete(f"/courses/{course_id}", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_nonexistent_course_returns_404(
    client: AsyncClient, auth_headers: dict
) -> None:
    """DELETE /courses/{id} for a non-existent course returns 404."""
    import uuid
    resp = await client.delete(f"/courses/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
