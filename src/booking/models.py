from datetime import date
import uuid

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    column,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.booking.constants import BookingStatus, MAX_NOTES_LENGTH
from src.cafes.models import Cafe
from src.database import Base
from src.users.models import User


class Booking(Base):
    """Модель бронирования.

    Представляет собой запись о бронировании стола в кафе на определённую дату.
    Одно бронирование связано с одним пользователем, одним кафе, одним
    временным слотом и одним столом.

    Relationships:
    user (User): Связь с пользователем. Обратная — `User.bookings`.
    cafe (Cafe): Связь с кафе. Обратная — `Cafe.bookings`.
    booking_table_slot (BookingTableSlot):
        Связь один-к-одному. Обратная — `BookingTableSlot.booking`.
        Позволяет получить забронированный стол и временной слот.

    Constraints:
        - Поле `booking_id` в `BookingTableSlot` уникально — гарантирует,
          что одна бронь связана только с одним столом и слотом.
    """

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False,
        comment='ID пользователя, который создал бронь',
    )
    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
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
        default=lambda: date.today(),  # дата в формате 'YYYY-MM-DD'
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
        default=BookingStatus.CREATED,
    )
    # --- связи ---
    # Один пользователь -> много бронирований
    user: Mapped['User'] = relationship(
        back_populates='bookings',
        lazy='selectin',
    )

    # Одно кафе -> много бронирований
    cafe: Mapped['Cafe'] = relationship(
        back_populates='bookings',
        lazy='selectin',
    )

    # Одна бронь -> один BookingTableSlot (one-to-one)
    booking_table_slot: Mapped['BookingTableSlot'] = relationship(
        back_populates='booking',
        uselist=False,
        lazy='selectin',
        cascade='all',
    )

    __table_args__ = (
        Index('ix_booking_user_id', user_id),
        Index('ix_booking_cafe_date', cafe_id, booking_date),
    )

    def activate_booking(self) -> None:
        """Активирует бронирование."""
        if self.booking_table_slot:
            self.booking_table_slot.restore()
        self.status = BookingStatus.ACTIVE

    def complete_booking(self) -> None:
        """Завершает бронирование."""
        if self.booking_table_slot:
            self.booking_table_slot.restore()
        self.status = BookingStatus.COMPLETED

    def cancel_booking(self) -> None:
        """Отменяет бронирование."""
        if self.booking_table_slot:
            self.booking_table_slot.soft_delete()
        self.status = BookingStatus.CANCELED

    def restore_booking(self) -> None:
        """Восстанавливает отменённое бронирование."""
        if self.booking_table_slot:
            self.booking_table_slot.restore()
        self.status = BookingStatus.CREATED


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
        - Уникальный `booking_id` (одна бронь — одна запись).
        - Уникальная комбинация `table_id`, `slot_id`, `booking_date` —
          предотвращает двойное бронирование одного стола в один и тот же слот
          и день для активной брони.
    """

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('booking.id', ondelete='CASCADE'),
        nullable=False,
        comment='Ссылка на бронь',
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('table.id', ondelete='CASCADE'),
        nullable=False,
        comment='Ссылка на забронированный стол',
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('slot.id', ondelete='CASCADE'),
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
    # Один к одному: одно бронирование --> одна запись BookingTableSlot
    booking: Mapped['Booking'] = relationship(
        back_populates='booking_table_slot',
        lazy='selectin',
    )
    # Один стол может быть забронирован несколько раз
    table: Mapped['Table'] = relationship(
        back_populates='booking_table_slots',
        lazy='selectin',
    )
    # Один временной слот может использоваться в нескольких бронях
    slot: Mapped['Slot'] = relationship(
        back_populates='booking_table_slots',
        lazy='selectin',
    )

    __table_args__ = (
        UniqueConstraint(
            'booking_id',
            name='unique_booking',
        ),
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
