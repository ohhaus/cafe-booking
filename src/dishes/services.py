# src/dishes/services.py
from typing import Sequence
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dishes.models import Dish
from src.database.service import DatabaseService, ModelType
from src.dishes.schemas import DishCreate, DishUpdate
from sqlalchemy.orm import selectinload


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

    # def __init__(self) -> None:
    #     """Инициализирует сервис для модели Dish."""
    #     super().__init__(Dish)

    async def get_dishes(
        self,
        session: AsyncSession,
        *,
        cafe_id: int | None = None,
        show_all: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dish]:
        """Получает список блюд с фильтрацией.

        Args:
            session: Асинхронная сессия БД
            cafe_id: ID кафе для фильтрации
            show_all: Показывать ли неактивные блюда
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей

        Returns:
            Список блюд
        """
        conditions = []

        if cafe_id is not None:
            conditions.append(Dish.cafe_id == cafe_id)

        if not show_all:
            conditions.append(Dish.active.is_(True))

        query = select(Dish)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.offset(skip).limit(limit)

        result = await session.execute(query)
        return result.scalars().all()

    async def get_active_dish(
        self,
        dish_id: int,
        session: AsyncSession,
    ) -> Dish | None:
        """Получает активное блюдо по ID.

        Args:
            dish_id: ID блюда
            session: Асинхронная сессия БД

        Returns:
            Блюдо или None
        """
        result = await session.execute(
            select(Dish).where(
                and_(
                    Dish.id == dish_id,
                    Dish.is_active.is_(True),
                )
            )
        )
        return result.scalars().first()


dish_service = DishService(Dish)
