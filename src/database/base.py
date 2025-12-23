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
    """Возвращает текущую дату и время в UTC."""
    return datetime.now(timezone.utc)


def resolve_table_name(class_name: str) -> str:
    """Генерирует имя таблицы из имени класса."""
    name = re.split('(?=[A-Z])', class_name)
    return '_'.join([x.lower() for x in name if x])


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy моделей."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    @property
    def is_active(self) -> bool:
        """Флаг активности, используемый при сериализации модели в JSON."""
        return self.active

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa
        return resolve_table_name(cls.__name__)

    def soft_delete(self) -> None:
        """Производит мягкое удаление записей."""
        self.active = False

    def restore(self) -> None:
        """Восстанавливает запись после мягкого удаления."""
        self.active = True
