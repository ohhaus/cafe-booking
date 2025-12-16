from typing import TYPE_CHECKING
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgres import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cafes.models import Cafe
from src.config import MAX_DESCRIPTION_LENGTH
from src.database import Base


if TYPE_CHECKING:
    from src.booking.models import BookingTableSlot


class Table(Base):
    """Модель столов.

    Relationships:
        cafe: Связь многие-к-одному с моделью Cafe.
            Каждый стол относится к одному кафе. На стороне Cafe доступен
            список столов через атрибут Cafe.tables. При удалении кафе
            все связанные столы удаляются (ondelete='CASCADE' на уровне БД
            и cascade='all, delete-orphan' на стороне Cafe).
        booking_table_slots: Связь один-ко-многим с BookingTableSlot.
            Через неё можно получить все бронирования, в которых участвует
            данный стол.

    Ограничения:
        - CHECK CONSTRAINT table_places_range:
          гарантирует, что count_place > 0 и count_place <= 20,
          то есть за столом не может быть ноль или отрицательное количество
          мест, и количество мест ограничено сверху бизнес-правилом
          (максимум 20).
    """

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        nullable=False,
    )
    count_place: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )

    cafe: Mapped['Cafe'] = relationship(
        back_populates='tables',
    )
    booking_table_slots: Mapped[list['BookingTableSlot']] = relationship(
        'BookingTableSlot',
        back_populates='table',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        CheckConstraint(
            'count_place > 0 and count_place <= 20',
            name='table_places_range',
        ),
    )
