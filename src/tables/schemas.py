from __future__ import annotations

from datetime import datetime
from typing import Optional, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.cafes.schemas import CafeShortInfo
from src.config import MAX_DESCRIPTION_LENGTH


class TableBase(BaseModel):
    """Общие поля для столов."""

    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание стола',
    )
    seat_number: int = Field(
        ...,
        ge=1,
        le=20,
        description='Количество мест за столом',
        # Стыкаовка с моделью, в модели поле называется count_place
        validation_alias='count_place',
    )

    model_config = ConfigDict(extra='forbid')


class TableCreate(TableBase):
    """Схема создания стола."""

    ...


class TableInfo(TableBase):
    """Полная информация о столе."""

    id: UUID
    is_active: bool = Field(
        # Стыкаовка с моделью, в модели поле называется active
        validation_alias='active',
        description='Активен ли стол',
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class TableWithCafeInfo(TableInfo):
    """Полная информация о столе с кафе."""

    cafe: CafeShortInfo


class TableShortInfo(TableBase):
    """Короткая информация о столе."""

    id: UUID

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class TableUpdate(BaseModel):
    """Схема для обновления стола."""

    description: Optional[str] = Field(
        default=None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание стола',
    )
    seat_number: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description='Количество мест за столом (1–20)',
    )
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def forbid_nulls(self) -> Self:
        """Запрет явного null в обновлении."""
        for field in ('description', 'seat_number', 'is_active'):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f'Поле {field} не может быть null')
        return self
