from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseRead(BaseModel):
    """Базовая схема для чтения объектов.

    Содержит общие поля, которые есть у всех моделей.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
