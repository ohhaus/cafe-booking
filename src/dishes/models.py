"""модель блюд кафе."""
from decimal import Decimal
from typing import Optional
import uuid

from sqlachemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgres import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    # relationship,
)

from src.config import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
)
from src.database import Base
from src.cafes.models import Cafe
# from src.photos.models import Photo
# from src.users.models import User, UserRole


# cafes_managers = Table(
#     'cafes_managers',
#     Base.metadata,
#     mapped_column(
#         'cafe_id',
#         UUID(as_uuid=True),
#         ForeignKey('cafe.id', ondelete='CASADE'),
#         primary_key=True,
#     ),
#     mapped_column(
#         'user_id',
#         UUID(as_uuid=True),
#         ForeignKey('user.id', ondelete='CASADE'),
#         primary_key=True,
#     ),
# )


class Dish(Base):
    """Модель блюда."""

    name: Mapped[str] = mapped_column(
        String(MAX_NAME_LENGTH),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(MAX_DESCRIPTION_LENGTH),
        nulable=True,
    )
    cafes_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('cafe.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    photo_id: Mapped[Optional[uuid:UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('photo.id', ondelete='SET NULL'),
        unique=True,
        nullable=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
