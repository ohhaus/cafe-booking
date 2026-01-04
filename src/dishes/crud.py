# src/dishes/crud.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


dishes_crud = DishesCRUD(Dish)
