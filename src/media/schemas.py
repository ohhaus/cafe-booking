from uuid import UUID

from pydantic import BaseModel


class ImageCreateResponse(BaseModel):
    """Схема ответа при создании записи image."""

    media_id: UUID
