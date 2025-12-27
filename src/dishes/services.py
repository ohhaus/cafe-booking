# src/dishes/services.py
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.service import DatabaseService, ModelType
from src.dishes.models import Dish
from src.dishes.schemas import DishCreate, DishUpdate


async def get_multi(
    self,
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[ModelType]:
    """Получает список объектов с загрузкой связей."""
    result = await session.execute(
        select(self.model)
        .options(selectinload(self.model.cafes))  # Загружаем связанные кафе
        .offset(skip)
        .limit(limit),
    )
    return result.scalars().all()


class DishService(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Сервис для работы с блюдами."""


dish_service = DishService(Dish)
