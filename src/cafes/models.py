from __future__ import annotations

from typing import Optional, TYPE_CHECKING

# import uuid
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
    pass

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
        dishes: Связь многие-ко-многим с блюдами (Dish) через
            промежуточную таблицу dishes_cafes. Позволяет получить все блюда,
            доступные в данном кафе.

    Ограничения:
        - Уникальность полей name, address и phone на уровне БД.
        - Внешние ключи с ondelete='CASCADE' для cafes_managers.cafe_id,
          slots.cafe_id и tables.cafe_id, обеспечивающие каскадное удаление
          связанных записей при удалении кафе.

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

    __table_args__ = (
        UniqueConstraint('name', 'address', name='uq_cafe_name_address'),
        Index('idx_cafe_name', 'name'),
    )
