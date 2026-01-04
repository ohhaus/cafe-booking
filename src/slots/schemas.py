from __future__ import annotations

from datetime import datetime, time
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


class TimeSlotBase(BaseModel):
    """Общие поля для слота бронирования."""

    start_time: time = Field(
        ...,
        description='Время начала слота',
        examples=['10:00:00'],
    )
    end_time: time = Field(
        ...,
        description='Время окончания слота',
        examples=['11:00:00'],
    )
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание слота',
    )

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def check_times(self) -> Self:
        """Проверяем, что start_time < end_time."""
        if self.start_time >= self.end_time:
            raise ValueError('start_time должен быть меньше end_time')
        return self


class TimeSlotCreate(TimeSlotBase):
    """Схема создания слота."""

    ...


class TimeSlotInfo(TimeSlotBase):
    """Полная информация о слоте."""

    id: UUID
    is_active: bool = Field(
        # Стыкаовка с моделью, в модели поле называется active
        validation_alias=AliasChoices('active', 'is_active'),
        description='Активен ли слот',
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class TimeSlotWithCafeInfo(TimeSlotInfo):
    """Информация о слоте с кафе."""

    cafe: CafeShortInfo


class TimeSlotShortInfo(BaseModel):
    """Короткая информация о слоте."""

    id: UUID
    start_time: time = Field(
        ...,
        description='Время начала слота',
    )
    end_time: time = Field(
        ...,
        description='Время окончания слота',
    )
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание слота',
    )

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class TimeSlotUpdate(BaseModel):
    """Схема для обновления слота."""

    start_time: Optional[time] = None
    end_time: Optional[time] = None
    description: Optional[str] = Field(
        default=None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description='Описание слота',
    )
    active: Optional[bool] = Field(
        default=None,
        alias='is_active',
    )

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def forbid_nulls(self) -> Self:
        """Запрещаем явные null в обновлении."""
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f'Поле {field} не может быть null')
        return self

    @model_validator(mode='after')
    def check_times(self) -> Self:
        """Если оба времени переданы — проверяем порядок."""
        if (
            'start_time' in self.model_fields_set
            and 'end_time' in self.model_fields_set
            and self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError('start_time должен быть меньше end_time')
        return self


class TimeSlotCreateDB(BaseModel):
    """Схема представления БД."""

    cafe_id: UUID
    start_time: time
    end_time: time
    description: Optional[str] = None

    model_config = ConfigDict(extra='forbid')
