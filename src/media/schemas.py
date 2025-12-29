from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImageCreateResponse(BaseModel):
    """Схема ответа при создании записи image."""

    media_id: UUID


class ImageCacheSchema(BaseModel):
    """Схема для кэширования данных об изображении."""

    id: UUID
    storage_path: str
    mime_type: str | None
    original_filename: str | None
    active: bool

    model_config = ConfigDict(from_attributes=True)
