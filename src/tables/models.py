import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String
)
from sqlalchemy.dialects.postgres import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.cafes.models import Cafe
from src.database import Base
from src.config import MAX_DESCRIPTION_LENGTH


class CafeTable(Base):
    """Модель столов."""

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        nullable=False,
    )
    count_place: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nullable=True,
    )

    cafe: Mapped['Cafe'] = relationship(
        back_populates='tables',
    )

    __table_args__ = (
        CheckConstraint(
            'count_place > 0 and count_place <= 20',
            name='table_places_range',
        ),
    )
