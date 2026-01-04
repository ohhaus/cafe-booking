from datetime import date
from typing import List, TYPE_CHECKING
import uuid

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    String,
    column,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.booking.constants import MAX_NOTES_LENGTH
from src.booking.enums import BookingStatus
from src.database import Base


if TYPE_CHECKING:
    from src.cafes.models import Cafe
    from src.slots.models import Slot
    from src.tables.models import Table
    from src.users.models import User


def date_today() -> date:
    """Возвращает текущую дату."""
    return date.today()


class Booking(Base):
    """Модель бронирования.

    Представляет собой запись о бронировании стола в кафе на определённую дату.
    Одно бронирование связано с одним пользователем, одним кафе, одним
    временным слотом и одним столом.

    Relationships:
    user (User): Связь с пользователем. Обратная — `User.bookings`.
    cafe (Cafe): Связь с кафе. Обратная — `Cafe.bookings`.
    booking_table_slots (BookingTableSlot):
        Связь один-ко-многим. Обратная — `BookingTableSlot.booking`.
        Позволяет получить забронированный стол и временной слот.
    """

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=False,
        comment='ID пользователя, который создал бронь',
    )
    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id'),
        comment='ID кафе, в котором создана бронь',
        nullable=False,
    )
    guest_number: Mapped[int] = mapped_column(
        comment='Количество гостей',
        nullable=False,
        default=1,
    )
    booking_date: Mapped[date] = mapped_column(
        Date,
        comment='Дата брони',
        default=date_today,
        nullable=False,
    )
    note: Mapped[str] = mapped_column(
        String(MAX_NOTES_LENGTH),
        comment='Примечание к брони',
        nullable=False,
        default='',
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name='booking_status', native_enum=True),
        comment='Статус брони',
        nullable=False,
        default=BookingStatus.BOOKING,
    )
    # --- связи ---
    # Один пользователь -> много бронирований
    user: Mapped['User'] = relationship(
        'User',
        back_populates='bookings',
        lazy='selectin',
    )

    # Одно кафе -> много бронирований
    cafe: Mapped['Cafe'] = relationship(
        'Cafe',
        back_populates='bookings',
        lazy='selectin',
    )

    # Одна бронь --> много столов и слотов
    booking_table_slots: Mapped[List['BookingTableSlot']] = relationship(
        'BookingTableSlot',
        back_populates='booking',
        uselist=True,
        lazy='selectin',
    )

    __table_args__ = (
        Index('ix_booking_user_id', user_id),
        Index('ix_booking_cafe_date', cafe_id, booking_date),
    )

    def cancel_booking(self) -> None:
        """Отменяет бронирование столов-слотов."""
        for bts in self.booking_table_slots:
            bts.active = False
        self.status = BookingStatus.CANCELED
        self.active = False

    def restore_booking(self) -> None:
        """Восстанавливает отменённое бронирование столов-слотов."""
        for bts in self.booking_table_slots:
            bts.active = True
        self.status = BookingStatus.BOOKING
        self.active = True


class BookingTableSlot(Base):
    """Модель связи бронирования, стола и временного слота.

    Обеспечивает уникальную привязку брони к столу и временному слоту на
    определённую дату.
    Также позволяет проверять, не забронирован ли стол на этот слот и дату.

    Relationships:
        booking (Booking): Обратная связь с бронированием.
        table (Table): Обратная связь с столом.
        slot (Slot): Обратная связь с временным слотом.

    Constraints:
        - Уникальная комбинация `table_id`, `slot_id`, `booking_date` —
          предотвращает двойное бронирование одного стола в один и тот же слот
          и день для активной брони.
    """

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('booking.id'),
        nullable=False,
        comment='Ссылка на бронь',
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('table.id'),
        nullable=False,
        comment='Ссылка на забронированный стол',
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('slot.id'),
        nullable=False,
        comment='Ссылка на временной слот',
    )
    booking_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment='Дата брони (копия из Booking, для уникальности '
        'стол+слот+дата)',
    )

    # --- связи ---
    # Один к многим: одно бронирование --> много столов и слотов
    booking: Mapped['Booking'] = relationship(
        'Booking',
        back_populates='booking_table_slots',
        lazy='selectin',
    )
    # Один стол может быть забронирован несколько раз
    table: Mapped['Table'] = relationship(
        'Table',
        back_populates='booking_table_slots',
        lazy='selectin',
    )
    # Один временной слот может использоваться в нескольких бронях
    slot: Mapped['Slot'] = relationship(
        'Slot',
        back_populates='booking_table_slots',
        lazy='selectin',
    )

    __table_args__ = (
        Index(
            'uq_table_slot_booking_date_when_active',
            'table_id',
            'slot_id',
            'booking_date',
            unique=True,
            postgresql_where=(column('active') == True),  # noqa: E712
        ),
        Index(
            'ix_booking_table_slot_table_date',
            table_id,
            booking_date,
        ),
        Index(
            'ix_booking_table_slot_slot_date',
            slot_id,
            booking_date,
        ),
    )
