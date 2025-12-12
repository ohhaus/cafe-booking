from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class BaseRead(BaseModel):
    """Базовая схема для чтения."""

    id: uuid4
    created_at: datetime
    updated_at: datetime
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
