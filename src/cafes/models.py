from __future__ import annotations

from typing import Optional, TYPE_CHECKING

# import uuid
from sqlalchemy import Column, ForeignKey, String, Table as SATable, and_
from sqlalchemy.dialects.postgres import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.config import (
    MAX_ADDRESS_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
)
from src.database import Base
from src.users.models import User, UserRole


# from src.photos.models import Photo


if TYPE_CHECKING:
    from src.booking.models import Booking
    from src.slots.models import Slot
    from src.tables.models import Table

#  Ассоциативная таблица для связи "многие к многим" моделей User и Cafe.
cafes_managers = SATable(
    'cafes_managers',
    Base.metadata,
    Column(
        'cafe_id',
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'user_id',
        UUID(as_uuid=True),
        ForeignKey('user.id', ondelete='CASCADE'),
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
        slots: Связь один-ко-многим со слотами бронирования (Slot).
            Каждый слот относится к одному кафе. При удалении кафе все
            связанные слоты удаляются (cascade='all, delete-orphan' на стороне
            Cafe, ondelete='CASCADE' на стороне Slot).
        tables: Связь один-ко-многим со столами (Table).
            Каждый стол относится к одному кафе. При удалении кафе все
            связанные столы удаляются (cascade='all, delete-orphan' на стороне
            Cafe, ondelete='CASCADE' на стороне Table).
        bookings: Связь один-ко-многим с бронированиями (Booking).
            Одно кафе может иметь множество бронирований. При удалении кафе
            все связанные брони удаляются (cascade='all, delete-orphan' на
            стороне Cafe, ondelete='CASCADE' на стороне Booking).

    Ограничения:
        - Уникальность полей name, address и phone на уровне БД.
        - Внешние ключи с ondelete='CASCADE' для cafes_managers.cafe_id,
          slots.cafe_id и tables.cafe_id, обеспечивающие каскадное удаление
          связанных записей при удалении кафе.

    """

    name: Mapped[str] = mapped_column(
        String(MAX_NAME_LENGTH),
        nullable=False,
        unique=True,
    )
    address: Mapped[str] = mapped_column(
        String(MAX_ADDRESS_LENGTH),
        nullable=False,
        unique=True,
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
        primaryjoin=id == cafes_managers.c.cafe_id,
        secondaryjoin=and_(
            User.id == cafes_managers.c.user_id,
            User.role == UserRole.MANAGER,
        ),
        viewonly=True,
        overlaps='managed_cafes, cafes',
    )
    # photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    #     UUID(as_uuid=True),
    #     ForeignKey('photo.id', ondelete='SET NULL'),
    #     unique=True,
    #     nullable=True,
    # )

    # photo: Mapped[Optional[Photo]] = relationship(
    #     back_populates='cafe',
    #     uselist=False,
    # )

    slots: Mapped[list['Slot']] = relationship(
        'Slot',
        back_populates='cafe',
        cascade='all, delete-orphan',
    )
    tables: Mapped[list['Table']] = relationship(
        'Table',
        back_populates='cafe',
        cascade='all, delete-orphan',
    )
    bookings: Mapped[list['Booking']] = relationship(
        'Booking',
        back_populates='cafe',
        cascade='all, delete-orphan',
    )
