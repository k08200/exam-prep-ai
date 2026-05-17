import uuid
from datetime import datetime

from pydantic import BaseModel


class MaterialResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    processing_status: str
    page_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialUploadResponse(BaseModel):
    materials: list[MaterialResponse]
    total_size: int
