from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ImageResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    storage_path: str
    uploaded_by_id: UUID
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    active: bool

    class Config:
        from_attributes = True
