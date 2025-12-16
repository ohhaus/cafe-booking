from datetime import time
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Time
from sqlalchemy.dialects.postgres import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cafes.models import Cafe
from src.database import Base


if TYPE_CHECKING:
    from src.booking.models import BookingTableSlot


class Slot(Base):
    """Модель временных слотов.

    Relationships:
        cafe: Связь многие-к-одному с моделью Cafe.
            Каждый слот относится к одному кафе. На стороне Cafe доступен
            список слотов через атрибут Cafe.slots. При удалении кафе все
            связанные слоты удаляются (ondelete='CASCADE', а также
            cascade='all, delete-orphan' на стороне Cafe).
        booking_table_slots: Связь один-ко-многим с BookingTableSlot.
            Используется для хранения конкретных бронирований, в которых
            участвует данный слот.

    Ограничения:
        - CHECK CONSTRAINT slot_start_before_end:
          гарантирует, что start_time < end_time, то есть слот имеет
          положительную длительность и не вырождается в нулевой интервал.
        - Уникальность cafe_id: один слот на одно кафе.
          (если потребуется несколько слотов на кафе, это ограничение
          нужно будет убрать).
    """

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
    )
    end_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
    )

    cafe: Mapped['Cafe'] = relationship(
        back_populates='slots',
    )
    booking_table_slots: Mapped[list['BookingTableSlot']] = relationship(
        'BookingTableSlot',
        back_populates='slot',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        CheckConstraint(
            'start_time < end_time',
            name='slot_start_before_end',
        ),
    )
