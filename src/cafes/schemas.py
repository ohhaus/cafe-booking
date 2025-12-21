from __future__ import annotations

from datetime import datetime
from typing import Optional, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import (
    MAX_ADDRESS_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
)
from src.users.schemas import PhoneStr, UserReadView


class UserReadInCafe(UserReadView):
    """Схема пользователя для предстваления внутри CafeInfo."""

    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class CafeBase(BaseModel):
    """Общая схема полей для кафе."""

    name: str = Field(
        ...,
        max_length=MAX_NAME_LENGTH,
        description='Название кафе',
    )
    address: str = Field(
        ...,
        max_length=MAX_ADDRESS_LENGTH,
        description='Адрес кафе',
    )
    phone: PhoneStr
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание кафе',
    )
    photo_id: UUID = Field(
        ...,
        description='UUID фото',
    )

    model_config = ConfigDict(extra='forbid')


class CafeCreate(CafeBase):
    """Схема создания объекта кафе."""

    managers_id: list[UUID] = Field(
        default_factory=list,
        description='Список UUID менеджеров',
    )


class CafeInfo(CafeBase):
    """Схема полной инфы о кафе."""

    id: UUID
    managers: list[UserReadInCafe] = Field(
        default_factory=list,
        description='Менеджеры кафе',
    )
    is_active: bool = Field(validation_alias='active')
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class CafeShortInfo(CafeBase):
    """Схема короткой инфыо кафе."""

    id: UUID

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class CafeUpdate(BaseModel):
    """Схема для обновления кафе."""

    name: str | None = None
    address: str | None = None
    phone: PhoneStr | None = None
    description: str | None = None
    photo_id: UUID | None = None
    managers_id: list[UUID] | None = None
    active: bool | None = Field(None, alias='is_active')

    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    @model_validator(mode='after')
    def forbid_nulls(self) -> Self:
        """Валидация явных Null в обновлении объекта."""
        for field in (
            'name',
            'address',
            'phone',
            'photo_id',
            'managers_id',
            'active',
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f'Поле {field} не может быть null')
        return self


class CafeCreateDB(BaseModel):
    """Схема представления БД."""

    name: str
    address: str
    phone: PhoneStr
    description: Optional[str] = None
    photo_id: UUID
