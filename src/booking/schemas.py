from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from src.booking.constants import MAX_BOOKING_DATE, MAX_GUEST_NUMBER
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
    count_place: int

    model_config = ConfigDict(from_attributes=True)


class SlotShortInfo(BaseModel):
    """Краткая информация о временном слоте."""

    id: UUID
    start_time: time
    end_time: time
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('start_time', 'end_time')
    def serialize_time(self, value: time) -> str:
        """Сериализовать time в строку в формате HH:MM."""
        return value.strftime('%H:%M')


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


def _validate_booking_date_in_range(booking_date: date) -> date:
    """Единая проверка диапазона даты брони (используется в CREATE и PATCH)."""
    today = date.today()
    max_date = today + timedelta(days=MAX_BOOKING_DATE)
    if not (today <= booking_date <= max_date):
        raise ValueError(
            'Дата бронирования должна быть в диапазоне от сегодня '
            f'до {MAX_BOOKING_DATE} дней вперёд.',
        )
    return booking_date


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
    status: BookingStatus = Field(
        default=BookingStatus.BOOKING,
        description='Только BOOKING и ACTIVE разрешены при создании.',
    )
    booking_date: date = Field(
        description='Должна быть в диапазоне от сегодня до MAX_BOOKING_DATE '
        'дней.',
    )

    model_config = ConfigDict(extra='forbid')

    @field_validator('status')
    @classmethod
    def validate_status(cls, booking_status: BookingStatus) -> BookingStatus:
        """Проверяет, что статус допустим при создании."""
        if booking_status not in (BookingStatus.BOOKING, BookingStatus.ACTIVE):
            raise ValueError(
                'При создании бронирования допустимы только статусы: '
                'BOOKING (0) или ACTIVE (2).',
            )
        return booking_status

    @field_validator('booking_date')
    @classmethod
    def validate_booking_date(cls, booking_date: date) -> date:
        """Проверяет, что дата в допустимом диапазоне."""
        return _validate_booking_date_in_range(booking_date)

    @model_validator(mode='after')
    def prevent_duplicate_pairs_in_create(self) -> Self:
        """Запрещает дублирующиеся пары в tables_slots."""
        pairs = [(ts.table_id, ts.slot_id) for ts in self.tables_slots]
        if len(pairs) != len(set(pairs)):
            raise ValueError(
                'Повторяющиеся (table_id, slot_id) в tables_slots '
                'недопустимы.',
            )
        return self


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
        gt=0,
        le=MAX_GUEST_NUMBER,
        description='Количество гостей должно быть больше 0 и не превышать '
        f'максимальное значение {MAX_GUEST_NUMBER}.',
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
        if self.tables_slots is not None:
            pairs = [(ts.table_id, ts.slot_id) for ts in self.tables_slots]
            if len(pairs) != len(set(pairs)):
                raise ValueError(
                    'Повторяющиеся (table_id, slot_id) в tables_slots '
                    'недопустимы.',
                )
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
                'Либо отмените бронь через status=CANCELED, либо не '
                'передавайте is_active.',
            )
        return self


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
