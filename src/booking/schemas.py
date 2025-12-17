from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from src.booking.constants import MAX_GUEST_NUMBER
from src.booking.models import BookingStatus


class UserShortInfo(BaseModel):
    """Краткая информация о пользователе."""

    id: UUID
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tg_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CafeShortInfo(BaseModel):
    """Краткая информация о кафе."""

    id: UUID
    name: str
    address: str
    phone: str
    description: Optional[str] = None
    photo_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class TableShortInfo(BaseModel):
    """Краткая информация о столе."""

    id: UUID
    description: Optional[str] = None
    seat_number: int

    model_config = ConfigDict(from_attributes=True)


class SlotShortInfo(BaseModel):
    """Краткая информация о временном слоте."""

    id: UUID
    start_time: str
    end_time: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TablesSlots(BaseModel):
    """Схема для привязки стола и временного слота при бронировании."""

    table_id: UUID
    slot_id: UUID


class TablesSlotsInfo(BaseModel):
    """Информация о связи брони со столом и слотом."""

    id: UUID
    table: TableShortInfo
    slot: SlotShortInfo

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    """Схема для создания бронирования."""

    cafe_id: UUID
    tables_slots: List[TablesSlots] = Field(
        min_length=1,
        description='Должен быть хотя бы один стол и слот.',
    )
    guest_number: int = Field(
        gt=0,
        le=MAX_GUEST_NUMBER,
        description='Количество гостей должно быть больше 0 и не превышать '
        f'максимальное значение {MAX_GUEST_NUMBER}.',
    )
    note: Optional[str] = None
    status: BookingStatus
    booking_date: date


class BookingInfo(BaseModel):
    """Полная информация о бронировании."""

    id: UUID
    user: UserShortInfo
    cafe: CafeShortInfo
    tables_slots: List[TablesSlotsInfo] = Field(
        validation_alias='booking_table_slots',
    )
    guest_number: int
    note: str
    status: BookingStatus
    booking_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('booking_date')
    def serialize_booking_date(self, value: date) -> str:
        """Сериализовать дату бронирования в ISO-формат (YYYY-MM-DD)."""
        return value.isoformat()  # → "2025-12-14"

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализовать дату и время из UTC в ISO-формат с Z (UTC)."""
        if value is None:
            return ''
        value = value.astimezone(timezone.utc)
        return value.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
