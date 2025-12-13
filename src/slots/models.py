from datetime import time
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Time,
)
from sqlalchemy.dialects.postgres import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.cafes.models import Cafe
from src.database import Base


class Slot(Base):
    """Модель временных слотов."""

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        unique=True,
        nullable=True,
    )
    start_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
    )
    end_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
    )

    cafe: Mapped['Cafe'] = relationship(
        back_populates='slot',
    )

    __table_args__ = (
        CheckConstraint(
            'start_time < end_time',
            name='slot_start_before_end',
        ),
    )
