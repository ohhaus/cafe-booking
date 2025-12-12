from typing import Optional
import uuid

from sqlalchemy import Column, ForeignKey, String, Table, and_
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
from src.photos.models import Photo
from src.users.models import User, UserRole


cafes_managers = Table(
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
    """Модель кафе."""

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
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('photo.id', ondelete='SET NULL'),
        unique=True,
        nullable=True,
    )

    photo: Mapped[Optional[Photo]] = relationship(
        back_populates='cafe',
        uselist=False,
    )
