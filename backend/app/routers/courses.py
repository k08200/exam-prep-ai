import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])


async def _build_course_response(course: Course, db: AsyncSession) -> CourseResponse:
    """Helper to attach computed fields: material_count and has_analysis."""
    material_status_result = await db.execute(
        select(Material.processing_status, func.count())
        .where(Material.course_id == course.id)
        .group_by(Material.processing_status)
    )
    material_counts = dict(material_status_result.all())
    completed_material_count = material_counts.get(PROCESSING_STATUS_COMPLETED, 0)
    processing_material_count = (
        material_counts.get(PROCESSING_STATUS_PENDING, 0)
        + material_counts.get(PROCESSING_STATUS_PROCESSING, 0)
    )
    failed_material_count = material_counts.get(PROCESSING_STATUS_FAILED, 0)
    material_count = sum(material_counts.values())

    analysis_result = await db.execute(
        select(ProfessorAnalysis.id).where(ProfessorAnalysis.course_id == course.id)
    )
    has_analysis = analysis_result.scalar_one_or_none() is not None

    data = {
        "id": course.id,
        "user_id": course.user_id,
        "name": course.name,
        "description": course.description,
        "professor_name": course.professor_name,
        "subject": course.subject,
        "created_at": course.created_at,
        "material_count": material_count,
        "completed_material_count": completed_material_count,
        "processing_material_count": processing_material_count,
        "failed_material_count": failed_material_count,
        "has_analysis": has_analysis,
    }
    return CourseResponse(**data)


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CourseResponse]:
    """Return all courses belonging to the current user."""
    result = await db.execute(
        select(Course).where(Course.user_id == current_user.id).order_by(Course.created_at.desc())
    )
    courses = result.scalars().all()
    return [await _build_course_response(c, db) for c in courses]


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_in: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CourseResponse:
    """Create a new course for the current user."""
    course = Course(
        user_id=current_user.id,
        name=course_in.name,
        description=course_in.description,
        professor_name=course_in.professor_name,
        subject=course_in.subject,
    )
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return await _build_course_response(course, db)


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CourseResponse:
    """Return a specific course by ID (must belong to current user)."""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return await _build_course_response(course, db)


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    course_update: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CourseResponse:
    """Update a course's metadata."""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    update_data = course_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)

    await db.flush()
    await db.refresh(course)
    return await _build_course_response(course, db)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a course and all its associated data."""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    material_paths_result = await db.execute(
        select(Material.file_path).where(Material.course_id == course_id)
    )
    for file_path in material_paths_result.scalars().all():
        Path(file_path).unlink(missing_ok=True)

    await db.delete(course)
    await db.commit()
