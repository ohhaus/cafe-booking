# src/dishes/crud.py

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cafes.models import Cafe
from src.database.service import DatabaseService
from src.dishes.models import Dish
from src.dishes.schemas import DishCreate, DishUpdate


class DishesCRUD(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Слой доступа к данным для бронирований."""

    async def get_active_cafes_by_ids(
            self,
            session: AsyncSession,
            cafes_ids: list[UUID],
    ) -> list[Cafe]:
        """Возвращает активные кафе по списку идентификаторов."""
        if not cafes_ids:
            return []

        res = await session.execute(
            select(Cafe).where(
                Cafe.id.in_(cafes_ids),
                Cafe.active.is_(True),
            ),
        )
        return list(res.scalars().all())

    async def get_by_id_with_cafes(
        self,
        *,
        session: AsyncSession,
        dish_id: UUID,
    ) -> Dish | None:
        stmt = (
            select(Dish)
            .where(Dish.id == dish_id)
            .options(selectinload(Dish.cafes))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_dish(
        self,
        *,
        session: AsyncSession,
        dish: Dish,
        data: dict[str, Any],
    ) -> Dish:
        for key, value in data.items():
            setattr(dish, key, value)

        await session.commit()
        await session.refresh(dish)
        return dish


dishes_crud = DishesCRUD(Dish)
