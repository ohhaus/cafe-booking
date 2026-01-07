from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MediaInfo(BaseModel):
    """Схема ответа при создании записи image."""

    media_id: UUID


class MediaData(BaseModel):
    """Загружаемый файл."""

    file: str = Field(
        ...,
        description='Загружаемый файл',
        json_schema_extra={'format': 'binary'},
    )


class ImageMediaSchema(BaseModel):
    """Схема для кэширования и валидации ImageMedia."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    storage_path: str
    uploaded_by_id: UUID
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
