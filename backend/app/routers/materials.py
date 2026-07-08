import os
import uuid
from datetime import datetime, timedelta, timezone
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
from app.models.analysis import ProfessorAnalysis
from app.models.material import (
    Material,
    PROCESSING_STATUS_COMPLETED,
    PROCESSING_STATUS_FAILED,
    PROCESSING_STATUS_PENDING,
    PROCESSING_STATUS_PROCESSING,
)
from app.models.user import User
from app.schemas.material import MaterialResponse, MaterialUploadResponse
from app.services.file_parser import FileParser
from app.services.material_quality import require_usable_extracted_text

router = APIRouter(tags=["materials"])
file_parser = FileParser()
STALE_PROCESSING_ERROR = "Processing did not finish. Please retry this material."
UPLOAD_CHUNK_SIZE = 1024 * 1024

# Map file extensions to internal file_type labels
EXTENSION_TO_TYPE: dict[str, str] = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".docx": "docx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}
LEGACY_OFFICE_EXTENSIONS: dict[str, str] = {
    ".ppt": "Legacy .ppt files are not supported. Convert the file to .pptx and upload again.",
    ".doc": "Legacy .doc files are not supported. Convert the file to .docx and upload again.",
}
GENERIC_UPLOAD_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
EXTENSION_TO_MIME_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".pptx": {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
    ".docx": {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    ".png": {"image/png"},
    ".jpg": {"image/jpeg", "image/pjpeg"},
    ".jpeg": {"image/jpeg", "image/pjpeg"},
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


async def _invalidate_course_analysis(course_id: uuid.UUID, db: AsyncSession) -> None:
    """Remove saved analysis when the material set changes."""
    result = await db.execute(
        select(ProfessorAnalysis).where(ProfessorAnalysis.course_id == course_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is not None:
        await db.delete(analysis)


def _validate_upload_content_type(upload_file: UploadFile, ext: str) -> None:
    """Reject obvious extension/content-type mismatches while allowing generic clients."""
    content_type = (upload_file.content_type or "").lower().split(";")[0].strip()
    if content_type in GENERIC_UPLOAD_MIME_TYPES:
        return

    expected = EXTENSION_TO_MIME_TYPES.get(ext, set())
    if expected and content_type not in expected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"File '{upload_file.filename or 'unknown'}' has content type "
                f"'{content_type}', which does not match extension '{ext}'."
            ),
        )


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
            material.extracted_text = require_usable_extracted_text(parsed.get("text"))
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


async def mark_stale_processing_materials(db: AsyncSession) -> int:
    """Mark abandoned pending/processing materials as failed so users can retry."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.MATERIAL_PROCESSING_STALE_MINUTES
    )
    result = await db.execute(
        select(Material).where(
            Material.processing_status.in_(
                [PROCESSING_STATUS_PENDING, PROCESSING_STATUS_PROCESSING]
            ),
            Material.created_at < cutoff,
        )
    )
    materials = result.scalars().all()
    for material in materials:
        material.processing_status = PROCESSING_STATUS_FAILED
        material.processing_error = STALE_PROCESSING_ERROR
    if materials:
        await db.commit()
    return len(materials)


async def recover_stale_processing_materials() -> int:
    """Startup recovery hook for background tasks lost during server restarts."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        return await mark_stale_processing_materials(session)


async def _save_upload_file(upload_file: UploadFile, file_path: Path) -> int:
    """Stream an uploaded file to disk and return the number of bytes written."""
    file_size = 0
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await upload_file.read(UPLOAD_CHUNK_SIZE):
                file_size += len(chunk)
                if file_size > settings.MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"File '{upload_file.filename or 'unknown'}' exceeds "
                            f"the {settings.MAX_FILE_SIZE // (1024 * 1024)} MB limit."
                        ),
                    )
                await f.write(chunk)
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    return file_size


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

    if len(files) > settings.MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Upload at most {settings.MAX_UPLOAD_FILES} files at a time.",
        )

    upload_dir = Path(settings.UPLOAD_DIR) / str(course_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    created_materials: list[Material] = []
    parse_tasks: list[tuple[uuid.UUID, str, str]] = []
    saved_paths: list[Path] = []
    total_size = 0

    for upload_file in files:
        original_filename = upload_file.filename or "unknown"
        ext = Path(original_filename).suffix.lower()
        if ext in LEGACY_OFFICE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=LEGACY_OFFICE_EXTENSIONS[ext],
            )
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{ext}' is not allowed. "
                       f"Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}",
            )
        _validate_upload_content_type(upload_file, ext)

    try:
        for upload_file in files:
            original_filename = upload_file.filename or "unknown"
            ext = Path(original_filename).suffix.lower()
            safe_filename = f"{uuid.uuid4()}{ext}"
            file_path = upload_dir / safe_filename

            file_size = await _save_upload_file(upload_file, file_path)
            saved_paths.append(file_path)

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
            parse_tasks.append((material.id, str(file_path), file_type))
            total_size += file_size
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    for material_id, file_path, file_type in parse_tasks:
        background_tasks.add_task(_parse_and_update, material_id, file_path, file_type)

    await _invalidate_course_analysis(course_id, db)

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


@router.post(
    "/courses/{course_id}/materials/{material_id}/retry",
    response_model=MaterialResponse,
)
async def retry_material_processing(
    course_id: uuid.UUID,
    material_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MaterialResponse:
    """Retry parsing for a failed material."""
    await _assert_course_ownership(course_id, current_user.id, db)

    result = await db.execute(
        select(Material).where(
            Material.id == material_id,
            Material.course_id == course_id,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    if material.processing_status in [PROCESSING_STATUS_PENDING, PROCESSING_STATUS_PROCESSING]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This material is already being processed.",
        )
    if material.processing_status == PROCESSING_STATUS_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This material has already been processed.",
        )
    if not Path(material.file_path).exists():
        material.processing_error = "Uploaded file is missing. Please delete and upload it again."
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=material.processing_error,
        )

    material.processing_status = PROCESSING_STATUS_PENDING
    material.processing_error = None
    material.extracted_text = None
    material.page_count = None
    await _invalidate_course_analysis(course_id, db)
    await db.flush()
    await db.refresh(material)

    background_tasks.add_task(
        _parse_and_update,
        material.id,
        material.file_path,
        material.file_type,
    )
    return MaterialResponse.model_validate(material)


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

    await _invalidate_course_analysis(course_id, db)
    await db.delete(material)
