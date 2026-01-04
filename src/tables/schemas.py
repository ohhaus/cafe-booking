from __future__ import annotations

from datetime import datetime
from typing import Optional, Self
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from src.cafes.schemas import CafeShortInfo
from src.config import MAX_DESCRIPTION_LENGTH


class TableBase(BaseModel):
    """Общие поля для столов."""

    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание стола',
    )
    count_place: int = Field(
        ...,
        ge=1,
        le=20,
        description='Количество мест за столом',
        alias='seat_number',
    )

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )


class TableCreate(TableBase):
    """Схема создания стола."""

    ...


class TableInfo(TableBase):
    """Полная информация о столе."""

    id: UUID
    is_active: bool = Field(
        validation_alias=AliasChoices('active', 'is_active'),
        description='Активен ли стол',
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra='forbid',
        populate_by_name=True,
    )


class TableWithCafeInfo(TableInfo):
    """Полная информация о столе с кафе."""

    cafe: CafeShortInfo


class TableShortInfo(TableBase):
    """Короткая информация о столе."""

    id: UUID

    model_config = ConfigDict(
        from_attributes=True,
        extra='forbid',
        populate_by_name=True,
    )


class TableUpdate(BaseModel):
    """Схема для обновления стола."""

    description: Optional[str] = Field(
        default=None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание стола',
    )
    count_place: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description='Количество мест за столом (1–20)',
        alias='seat_number',
    )
    active: Optional[bool] = Field(
        default=None,
        alias='is_active',
    )

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def forbid_nulls(self) -> Self:
        """Запрет явного null в обновлении."""
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f'Поле {field} не может быть null')
        return self


class TableCreateDB(BaseModel):
    """Схема представления БД."""

    description: str | None = None
    count_place: int
    cafe_id: UUID

    model_config = ConfigDict(extra='forbid')
