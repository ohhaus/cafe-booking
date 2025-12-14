import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, ForeignKey, Numeric, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH
from src.database import Base

# Промежуточная таблица для связи между блюдами и кафе
dish_cafe = Table(
    'dishes_cafes',
    Base.metadata,
    Column(
        'dish_id',
        UUID(as_uuid=True),
        ForeignKey('dish.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'cafe_id',
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)


class Dish(Base):
    """Модель блюда в кафе."""

    name: Mapped[str] = mapped_column(
        String(MAX_NAME_LENGTH),
        nullable=False,
        unique=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )
    # todo: добавить связь с фото/медиа
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
