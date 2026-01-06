# src/common/schemas.py
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class BaseRead(BaseModel):
    """Базовая схема для чтения объектов.

    Содержит общие поля, которые есть у всех моделей.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализовать дату и время из UTC в ISO-формат с Z (UTC)."""
        if value is None:
            return ''
        value = value.astimezone(timezone.utc)
        return value.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


class CustomErrorResponse(BaseModel):
    """Схема для пользовательских ошибок."""

    code: int
    message: str

    model_config = ConfigDict(from_attributes=True)
