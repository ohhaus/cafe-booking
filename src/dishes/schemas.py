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
    UUID_LENGTH,
)


class BaseDish(BaseModel):
    """Базовая схема блюда."""

    name: str = Field(..., max_length=MAX_NAME_LENGTH)
    description: Optional[str]
    photo_id: Optional[UUID]
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        min_length=MIN_DESCRIPTION_LENGTH,
    )
    photo_id: Optional[str] = Field(None, max_length=UUID_LENGTH)
    price: int = Field(..., ge=DISH_MIN_PRICE, le=DISH_MAX_PRICE)


class DishCreate(BaseDish):
    """Создание блюда."""

    price: int = Field(gt=DISH_MIN_PRICE, le=DISH_MAX_PRICE)
    cafes_id: list[int]


class DishUpdate(BaseModel):
    """Обновление блюда."""

    name: Optional[str] = Field(None, max_length=MAX_NAME_LENGTH)
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        min_length=MIN_DESCRIPTION_LENGTH,
    )
    photo_id: Optional[str] = Field(None, max_length=UUID_LENGTH)
    price: Optional[int] = Field(None, ge=DISH_MIN_PRICE, le=DISH_MAX_PRICE)
    cafes_id: Optional[List[int]]
    is_active: bool = True
    price: int = Field(gt=0)


class DishShortInfo(BaseDish):
    """Отдача информации о блюде."""

    id: int
    model_config = ConfigDict(from_attributes=True)


class DishInfo(DishShortInfo):
    """Отдача информации о блюде."""

    is_active: bool = True
    cafes: List[CafeShortInfo]

    model_config = ConfigDict(from_attributes=True)
