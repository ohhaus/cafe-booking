"""Модуль базовой конфигурации SQLAlchemy ORM.

Содержит базовый класс для всех моделей с общими полями и методами.
Предоставляет автоматическую генерацию имен таблиц, временные метки UTC
и поддержку мягкого удаления.
"""

from datetime import datetime, timezone
import re
import uuid

from sqlalchemy import Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)


def now_utc() -> datetime:
    """Возвращает текущую дату и время в UTC.

    Returns:
        datetime: Текущая дата и время с часовым поясом UTC.

    """
    return datetime.now(timezone.utc)


def resolve_table_name(class_name: str) -> str:
    """Генерирует имя таблицы из имени класса в стиле snake_case.

    Args:
        class_name: Имя класса в CamelCase.

    Returns:
        str: Имя таблицы в snake_case.

    """
    name = re.split('(?=[A-Z])', class_name)
    return '_'.join([x.lower() for x in name if x])


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy моделей.

    Предоставляет общие поля и методы для всех моделей:
    - UUID первичный ключ
    - Автоматические временные метки создания и обновления
    - Поддержка мягкого удаления
    - Автоматическое именование таблиц

    Attributes:
        id (Mapped[uuid.UUID]): Уникальный идентификатор записи.
        created_at (Mapped[datetime]): Дата и время создания записи в UTC.
        updated_at (Mapped[datetime]): Дата и время обновления записи в UTC.
        active (Mapped[bool]): Флаг активности записи (для мягкого удаления).

    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc='Уникальный идентификатор записи в формате UUID',
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
        doc='Дата и время создания записи в UTC',
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
        doc='Дата и время последнего обновления записи в UTC',
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc='Флаг активности записи (True - активна, False - удалена)',
    )

    @property
    def is_active(self) -> bool:
        """Флаг активности для сериализации в JSON.

        Returns:
            bool: True если запись активна, False если удалена.

        """
        return self.active

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        """Автоматически генерирует имя таблицы из имени класса.

        Returns:
            str: Имя таблицы в snake_case.

        """
        return resolve_table_name(cls.__name__)
