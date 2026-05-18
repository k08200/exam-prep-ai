import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.course import Course
from app.models.material import (
    Material,
    PROCESSING_STATUS_COMPLETED,
    PROCESSING_STATUS_FAILED,
    PROCESSING_STATUS_PROCESSING,
)
from app.models.user import User
from app.schemas.material import MaterialResponse, MaterialUploadResponse
from app.services.file_parser import FileParser

router = APIRouter(tags=["materials"])
file_parser = FileParser()

# Map file extensions to internal file_type labels
EXTENSION_TO_TYPE: dict[str, str] = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".docx": "docx",
    ".doc": "docx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


async def _assert_course_ownership(
    course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Course:
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return course


async def _parse_and_update(material_id: uuid.UUID, file_path: str, file_type: str) -> None:
    """Background task: parse a file and persist the extracted text."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Material).where(Material.id == material_id)
            )
            material = result.scalar_one_or_none()
            if material is None:
                return

            material.processing_status = PROCESSING_STATUS_PROCESSING
            material.processing_error = None
            await session.flush()

            parsed = await file_parser.parse_file(file_path, file_type)
            material.extracted_text = parsed["text"]
            material.page_count = parsed.get("page_count")
            material.processing_status = PROCESSING_STATUS_COMPLETED
            material.processing_error = None

            await session.commit()
        except Exception as exc:
            await session.rollback()
            # Try to mark the material as failed
            try:
                result = await session.execute(
                    select(Material).where(Material.id == material_id)
                )
                material = result.scalar_one_or_none()
                if material:
                    material.processing_status = PROCESSING_STATUS_FAILED
                    material.processing_error = str(exc)
                    await session.commit()
            except Exception:
                pass


@router.post(
    "/courses/{course_id}/materials",
    response_model=MaterialUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_materials(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MaterialUploadResponse:
    """Upload one or more files to a course. Parsing happens in the background."""
    await _assert_course_ownership(course_id, current_user.id, db)

    upload_dir = Path(settings.UPLOAD_DIR) / str(course_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    created_materials: list[Material] = []
    total_size = 0

    for upload_file in files:
        original_filename = upload_file.filename or "unknown"
        ext = Path(original_filename).suffix.lower()

        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{ext}' is not allowed. "
                       f"Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}",
            )

        # Read first chunk to determine size without loading everything into memory
        content = await upload_file.read()
        file_size = len(content)

        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{original_filename}' exceeds the 50 MB limit.",
            )

        safe_filename = f"{uuid.uuid4()}{ext}"
        file_path = upload_dir / safe_filename

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        file_type = EXTENSION_TO_TYPE.get(ext, "unknown")
        material = Material(
            course_id=course_id,
            filename=safe_filename,
            original_filename=original_filename,
            file_type=file_type,
            file_path=str(file_path),
            file_size=file_size,
        )
        db.add(material)
        await db.flush()
        await db.refresh(material)
        created_materials.append(material)
        total_size += file_size

        # Schedule background parsing after committing
        background_tasks.add_task(
            _parse_and_update, material.id, str(file_path), file_type
        )

    responses = [MaterialResponse.model_validate(m) for m in created_materials]
    return MaterialUploadResponse(materials=responses, total_size=total_size)


@router.get("/courses/{course_id}/materials", response_model=list[MaterialResponse])
async def list_materials(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MaterialResponse]:
    """List all materials for a course."""
    await _assert_course_ownership(course_id, current_user.id, db)
    result = await db.execute(
        select(Material)
        .where(Material.course_id == course_id)
        .order_by(Material.created_at.asc())
    )
    materials = result.scalars().all()
    return [MaterialResponse.model_validate(m) for m in materials]


@router.delete(
    "/courses/{course_id}/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_material(
    course_id: uuid.UUID,
    material_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a material file record and the associated file on disk."""
    await _assert_course_ownership(course_id, current_user.id, db)

    result = await db.execute(
        select(Material).where(
            Material.id == material_id, Material.course_id == course_id
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    file_path = Path(material.file_path)
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    await db.delete(material)
