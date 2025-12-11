from datetime import datetime, timezone
import re
import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)


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
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa
        return resolve_table_name(cls.__name__)
