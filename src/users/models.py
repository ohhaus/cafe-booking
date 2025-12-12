from enum import IntEnum
from typing import Optional

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import (
    MAX_PHONE_LENGTH,
    MAX_STRING_LENGTH,
    MAX_TG_LENGTH,
    MAX_USERNAME_LENGTH,
)
from src.database import Base


class UserRole(IntEnum):
    """IntEnum для ролей пользователей."""

    USER = 0
    MANAGER = 1
    ADMIN = 2


class User(Base):
    """Модель для пользователей."""

    username: Mapped[str] = mapped_column(
        String(MAX_USERNAME_LENGTH),
        unique=True,
        nullable=False,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(MAX_STRING_LENGTH),
        unique=True,
        nullable=True,
    )
    phone: Mapped[str] = mapped_column(
        String(MAX_PHONE_LENGTH),
        unique=True,
        nullable=False,
    )
    tg_id: Mapped[Optional[str]] = mapped_column(
        String(MAX_TG_LENGTH),
        unique=True,
        nullable=True,
    )
    role: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=UserRole.USER,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(MAX_STRING_LENGTH),
        nullable=False,
    )

    cafes = relationship(  # : Mapped[List["Cafe"]]
        "Cafe",
        secondary="cafes_managers",
        back_populates="managers",
        lazy="selectin",
        init=False,
    )
    bookings = relationship(  # : Mapped[List["Booking"]]
        "Booking",
        back_populates="user",
        lazy="selectin",
        init=False,
    )

    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="check_email_or_phone_not_null",
        ),
    )

    def is_admin(self) -> bool:
        """Определяет, является ли пользователь администратором."""
        return self.role == UserRole.ADMIN

    def is_manager(self) -> bool:
        """Определяет, является ли пользователь менеджером."""
        return self.role == UserRole.MANAGER

    def is_user(self) -> bool:
        """Определяет, является ли пользователь обычным user'ом."""
        return self.role == UserRole.USER

    def is_staff(self) -> bool:
        """Определяет, является ли пользователь представителем персонала."""
        return self.is_admin() or self.is_manager()
