from datetime import date, timedelta
from typing import List, Optional, Self, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from src.booking.constants import (
    BookingStatus,
    MAX_BOOKING_DATE,
    MAX_GUEST_NUMBER,
)
from src.cafes.schemas import CafeShortInfo
from src.common import BaseRead
from src.slots.schemas import TimeSlotShortInfo
from src.tables.schemas import TableShortInfo
from src.users.schemas import UserReadView


T = TypeVar('T', bound='BookingBase')


class TablesSlots(BaseModel):
    """Схема для привязки стола и временного слота при бронировании."""

    table_id: UUID
    slot_id: UUID


class TablesSlotsInfo(BaseModel):
    """Информация о связи брони со столом и слотом."""

    id: UUID
    table: TableShortInfo
    slot: TimeSlotShortInfo
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


def _validate_booking_date_in_range(booking_date: date) -> date:
    """Единая проверка диапазона даты брони (используется в CREATE и PATCH)."""
    today = date.today()
    max_date = today + timedelta(days=MAX_BOOKING_DATE)
    if not (today <= booking_date <= max_date):
        raise ValueError(
            'Дата бронирования должна быть в диапазоне от сегодня до '
            f'{MAX_BOOKING_DATE} дней вперёд.',
        )
    return booking_date


def _prevent_duplicate_pairs_validator(
    tables_slots: Optional[List[TablesSlots]],
) -> None:
    """Проверяет, что в списке tables_slots нет дублирующихся пар."""
    if tables_slots is None:
        return
    pairs = [(ts.table_id, ts.slot_id) for ts in tables_slots]
    if len(pairs) != len(set(pairs)):
        raise ValueError(
            'Повторяющиеся (table_id, slot_id) в tables_slots недопустимы.',
        )


def _validate_guest_number_range(value: Optional[int]) -> Optional[int]:
    """Проверяет, что guest_number в допустимом диапазоне."""
    if value is None:
        return value
    if value <= 0:
        raise ValueError('Количество гостей должно быть больше 0.')
    if value > MAX_GUEST_NUMBER:
        raise ValueError(
            f'Количество гостей не может превышать {MAX_GUEST_NUMBER}.',
        )
    return value


class BookingBase(BaseModel):
    """Базовая схема бронирования, содержащая общие поля."""

    cafe_id: UUID
    tables_slots: List[TablesSlots] = Field(
        min_length=1,
        description='Должен быть хотя бы один стол и слот.',
    )
    guest_number: int = Field(
        description='Количество гостей должно быть больше 0 и не превышать '
        f'{MAX_GUEST_NUMBER}.',
    )
    note: Optional[str] = None
    booking_date: date = Field(
        description='Должна быть в диапазоне от сегодня до '
        f'{MAX_BOOKING_DATE} дней.',
    )

    model_config = ConfigDict(extra='forbid')

    @field_validator('booking_date')
    @classmethod
    def validate_booking_date(cls, booking_date: date) -> date:
        """Проверяет, что дата в допустимом диапазоне."""
        return _validate_booking_date_in_range(booking_date)

    @field_validator('guest_number')
    @classmethod
    def validate_guest_number(cls, value: int) -> int:
        """Проверяет, что количество гостей в допустимом диапазоне."""
        return _validate_guest_number_range(value)

    @model_validator(mode='after')
    def prevent_duplicate_pairs(self) -> Self:
        """Запрещает дублирующиеся пары (table_id, slot_id) в tables_slots."""
        _prevent_duplicate_pairs_validator(self.tables_slots)
        return self


class BookingCreate(BookingBase):
    """Схема для создания бронирования."""

    status: BookingStatus = Field(
        default=BookingStatus.BOOKING,
        description='Только BOOKING и ACTIVE разрешены при создании.',
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, status: BookingStatus) -> BookingStatus:
        """Проверяет, что статус допустим при создании."""
        if status not in (BookingStatus.BOOKING, BookingStatus.ACTIVE):
            raise ValueError(
                'При создании бронирования допустимы только статусы: '
                'BOOKING (0) или ACTIVE (2).',
            )
        return status


class BookingUpdate(BaseModel):
    """Схема для обновления бронирования."""

    cafe_id: Optional[UUID] = None
    tables_slots: Optional[List[TablesSlots]] = Field(
        None,
        min_length=1,
        description='Должен быть хотя бы один стол и слот.',
    )
    guest_number: Optional[int] = Field(
        None,
        description='Количество гостей должно быть больше 0 и не превышать '
        f'{MAX_GUEST_NUMBER}.',
    )
    note: Optional[str] = None
    status: Optional[BookingStatus] = None
    booking_date: Optional[date] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra='forbid')

    @field_validator('booking_date')
    @classmethod
    def validate_booking_date_if_provided(
        cls,
        booking_date: Optional[date],
    ) -> Optional[date]:
        """Проверяет дату в PATCH только если она передана."""
        if booking_date is None:
            return booking_date
        return _validate_booking_date_in_range(booking_date)

    @field_validator('guest_number')
    @classmethod
    def validate_guest_number_in_update(
        cls,
        value: Optional[int],
    ) -> Optional[int]:
        """Проверяет, что количество гостей в допустимом диапазоне."""
        return _validate_guest_number_range(value)

    @model_validator(mode='after')
    def forbid_nulls(self) -> Self:
        """Запрещает передачу явных null-значений для любых полей."""
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f'Поле {field} не может быть null')
        return self

    @model_validator(mode='after')
    def prevent_duplicate_pairs_in_update(self) -> Self:
        """Запрещает дублирующиеся пары в tables_slots."""
        _prevent_duplicate_pairs_validator(self.tables_slots)
        return self

    @model_validator(mode='after')
    def validate_status_is_active_consistency(self) -> Self:
        """Проверяет согласованность status и is_active."""
        if self.status is None or self.is_active is None:
            return self

        if self.status == BookingStatus.CANCELED and self.is_active is True:
            raise ValueError(
                'Нельзя одновременно установить status=CANCELED и '
                'is_active=true.',
            )
        if self.status != BookingStatus.CANCELED and self.is_active is False:
            raise ValueError(
                'Нельзя одновременно установить status!=CANCELED и '
                'is_active=false. '
                'Либо отмените бронь через status=CANCELED, '
                'либо не передавайте is_active.',
            )
        return self


class BookingInfo(BaseRead):
    """Полная информация о бронировании."""

    user: UserReadView
    cafe: CafeShortInfo
    tables_slots: List[TablesSlotsInfo] = Field(
        validation_alias='booking_table_slots',
    )
    guest_number: int
    note: str
    status: BookingStatus
    booking_date: date

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('booking_date')
    def serialize_booking_date(self, value: date) -> str:
        """Сериализовать дату бронирования в ISO-формат (YYYY-MM-DD)."""
        return value.isoformat()
