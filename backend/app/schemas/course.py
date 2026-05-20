import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    professor_name: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=255)


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    professor_name: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=255)


class CourseResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    professor_name: str | None
    subject: str | None
    created_at: datetime
    material_count: int = 0
    completed_material_count: int = 0
    processing_material_count: int = 0
    failed_material_count: int = 0
    has_analysis: bool = False

    model_config = {"from_attributes": True}
