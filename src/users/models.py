from enum import IntEnum

from constants import (
    MAX_PHONE_LENGTH,
    MAX_STRING_LENGTH,
    MAX_TG_LENGTH,
    MAX_USERNAME_LENGTH,
)
from sqlalchemy import CheckConstraint, Column, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class UserRole(IntEnum):
    """IntEnum для ролей пользователей."""

    USER = 0
    MANAGER = 1
    ADMIN = 2


class User(Base):
    """Модель для пользователей."""

    username = Column(String(MAX_USERNAME_LENGTH), unique=True)
    email = Column(String(MAX_STRING_LENGTH), unique=True, nullable=True)
    phone = Column(String(MAX_PHONE_LENGTH), unique=True)
    tg_id = Column(String(MAX_TG_LENGTH), unique=True)
    role = Column(Integer, nullable=False, default=UserRole.USER)
    hashed_password = Column(String(MAX_STRING_LENGTH), nullable=False)

    cafes = relationship(
        'Cafe',
        secondary='user_cafe',
        back_populates='managers',
        lazy='selectin',
    )

    bookings = relationship('Booking', back_populates='user', lazy='selectin')

    __table_args__ = (
        CheckConstraint(
            'email IS NOT NULL OR phone IS NOT NULL',
            name='check_email_or_phone_not_null',
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
