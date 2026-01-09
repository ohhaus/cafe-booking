# src/actions/schemas.py
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.cafes.schemas import CafeShortInfo
from src.config import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH


class BaseAction(BaseModel):
    """Базовая схема акции."""

    name: str = Field(..., max_length=MAX_NAME_LENGTH)
    description: str = Field(
        ...,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание акции',
    )
    photo_id: Optional[UUID] = Field(
        None,
        description='UUID изображения акции',
    )


class ActionCreate(BaseAction):
    """Создание акции."""

    cafes_id: List[UUID] = Field(
        ...,
        max_length=1,
        description='Список ID кафе, где проводится акция',
    )


class ActionUpdate(BaseModel):
    """Обновление акции."""

    name: Optional[str] = Field(
        None,
        max_length=MAX_NAME_LENGTH,
        description='Название акции',
    )
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание акции',
    )
    photo_id: Optional[UUID] = Field(
        None,
        description='UUID изображения акции',
    )
    cafes_id: Optional[List[UUID]] = Field(
        None,
        min_length=1,
        description='Список ID кафе, где проводится акция',
    )
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra='forbid')


class ActionInfo(BaseAction):
    """Полная информация об акции."""

    id: UUID
    cafes: List[CafeShortInfo] = []
    is_active: bool = Field(
        True,
        description='Активна ли акция',
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class ActionShortInfo(BaseAction):
    """Краткая информация об акции."""

    id: UUID
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
