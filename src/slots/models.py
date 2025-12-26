from datetime import time
from typing import Optional, TYPE_CHECKING
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.booking.models import BookingTableSlot
from src.config import MAX_DESCRIPTION_LENGTH
from src.database.base import Base


if TYPE_CHECKING:
    from src.cafes.models import Cafe


class Slot(Base):
    """Модель временных слотов.

    Ограничения:
        - CHECK CONSTRAINT slot_start_before_end:
          гарантирует, что start_time < end_time, то есть слот имеет
          положительную длительность и не вырождается в нулевой интервал.
    """

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id'),
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
    description: Mapped[Optional[str]] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )
    # Связи
    booking_table_slots: Mapped[list['BookingTableSlot']] = relationship(
        back_populates='slot',
        uselist=True,
        lazy='selectin',
    )
    cafe: Mapped['Cafe'] = relationship(
        'Cafe',
        back_populates='slots',
        lazy='selectin',
    )

    __table_args__ = (
        CheckConstraint(
            'start_time < end_time',
            name='slot_start_before_end',
        ),
    )
