# src/dishes/schemas.py
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.booking.schemas import CafeShortInfo
from src.config import (
    DISH_MAX_PRICE,
    DISH_MIN_PRICE,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MIN_DESCRIPTION_LENGTH,
)


class BaseDish(BaseModel):
    """Базовая схема блюда."""

    name: str
    description: str | None = None
    photo_id: UUID

    price: Decimal = Field(
        ...,
        ge=DISH_MIN_PRICE,
        le=DISH_MAX_PRICE,
        multiple_of=Decimal('0.01'),
        examples=[DISH_MAX_PRICE],
    )


class DishCreate(BaseDish):
    """Схема блюда для создания нового."""

    cafes_id: list[UUID]


class DishUpdate(BaseModel):
    """Схема блюда для обновления."""

    name: Optional[str] = Field(None, max_length=MAX_NAME_LENGTH)
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        min_length=MIN_DESCRIPTION_LENGTH,
    )
    photo_id: Optional[UUID] = None
    price: Optional[Decimal] = Field(
        None,
        ge=DISH_MIN_PRICE,
        le=DISH_MAX_PRICE,
        )
    cafes_id: Optional[List[UUID]] = None
    is_active: Optional[bool] = None


class DishInfo(BaseDish):
    """Полная информации о блюде."""

    id: UUID
    cafes: list[CafeShortInfo] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
