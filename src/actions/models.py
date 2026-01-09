from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config import MAX_NAME_LENGTH
from src.database import Base


if TYPE_CHECKING:
    from src.cafes.models import Cafe

# Промежуточная таблица для связи между акциями и кафе
actions_cafes = Table(
    'actions_cafes',
    Base.metadata,
    Column(
        'action_id',
        UUID(as_uuid=True),
        ForeignKey('action.id'),
        primary_key=True,
    ),
    Column(
        'cafe_id',
        UUID(as_uuid=True),
        ForeignKey('cafe.id'),
        primary_key=True,
    ),
)


class Action(Base):
    """Модель акции в кафе.

    Relationships:
        cafes: Связь многие-ко-многим с кафе (Cafe) через промежуточную
        таблицу actions_cafes.
        Позволяет получить все кафе, в которых проводится данная акция.
    """

    name: Mapped[str] = mapped_column(
        String(MAX_NAME_LENGTH),
        nullable=False,
        unique=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Связь многие-ко-многим с Cafe
    cafes: Mapped[list['Cafe']] = relationship(
        'Cafe',
        secondary=actions_cafes,
        back_populates='actions',
        lazy='selectin',
    )
