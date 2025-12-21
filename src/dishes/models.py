from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import uuid

from sqlalchemy import Column, ForeignKey, Numeric, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH
from src.database import Base


if TYPE_CHECKING:
    from src.booking.models import Cafe

# Промежуточная таблица для связи между блюдами и кафе
dish_cafe = Table(
    'dishes_cafes',
    Base.metadata,
    Column(
        'dish_id',
        UUID(as_uuid=True),
        ForeignKey('dish.id'),
        primary_key=True,
    ),
    Column(
        'cafe_id',
        UUID(as_uuid=True),
        ForeignKey('cafe.id'),
        primary_key=True,
    ),
)


class Dish(Base):
    """Модель блюда в кафе.

    Relationships:
        cafes: Связь многие-ко-многим с кафе (Cafe) через промежуточную
        таблицу dishes_cafes.
        Позволяет получить все кафе, в которых доступно данное блюдо.
    """

    name: Mapped[str] = mapped_column(
        String(MAX_NAME_LENGTH),
        nullable=False,
        unique=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # Связь многие-ко-многим с Cafe
    cafes: Mapped[list['Cafe']] = relationship(
        'Cafe',
        secondary=dish_cafe,
        back_populates='dishes',
    )
