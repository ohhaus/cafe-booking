from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    String,
    Table as SATable,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.booking.models import Booking
from src.config import (
    MAX_ADDRESS_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
)
from src.database.base import Base
from src.media.models import ImageMedia
from src.users.models import User, UserRole


if TYPE_CHECKING:
    from src.slots.models import Slot
    from src.tables.models import Table


#  Ассоциативная таблица для связи "многие к многим" моделей User и Cafe.
cafes_managers = SATable(
    'cafes_managers',
    Base.metadata,
    Column(
        'cafe_id',
        UUID(as_uuid=True),
        ForeignKey('cafe.id'),
        primary_key=True,
    ),
    Column(
        'user_id',
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        primary_key=True,
    ),
)


class Cafe(Base):
    """Модель кафе.

    Relationships:
        managers: Связь многие-ко-многим с пользователями (User) через
            промежуточную таблицу cafes_managers. В выборку попадают только
            пользователи с ролью MANAGER. Связь доступна только для чтения
            (viewonly=True).

    Ограничения:
        - Уникальность полей name, address и phone на уровне БД.
    """

    name: Mapped[str] = mapped_column(
        String(MAX_NAME_LENGTH),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(
        String(MAX_ADDRESS_LENGTH),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(MAX_PHONE_LENGTH),
        nullable=False,
        unique=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )
    managers: Mapped[list[User]] = relationship(
        'User',
        secondary=cafes_managers,
        primaryjoin=id == cafes_managers.columns.cafe_id,
        secondaryjoin=and_(
            User.id == cafes_managers.columns.user_id,
            User.role == UserRole.MANAGER,
            User.active.is_(True),
        ),
        viewonly=True,
        overlaps='managed_cafes, cafes',
    )
    photo_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('image_media.id'),
        unique=True,
        nullable=True,
    )

    #  Связи
    bookings: Mapped[list['Booking']] = relationship(
        'Booking',
        back_populates='cafe',
        lazy='selectin',
    )
    # dishes: Mapped[list['Dish']] = relationship(
    #     'Dish',
    #     secondary='dishes_cafes',
    #     back_populates='cafes',
    # )
    tables: Mapped[list['Table']] = relationship(
        'Table',
        back_populates='cafe',
        lazy='selectin',
    )
    slots: Mapped[list['Slot']] = relationship(
        'Slot',
        back_populates='cafe',
        lazy='selectin',
    )
    photo: Mapped[Optional['ImageMedia']] = relationship(
        'ImageMedia',
        lazy='selectin',
        foreign_keys={photo_id},
    )

    __table_args__ = (
        UniqueConstraint('name', 'address', name='uq_cafe_name_address'),
        Index('idx_cafe_name', 'name'),
    )
