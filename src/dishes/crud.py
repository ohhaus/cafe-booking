from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.database.service import DatabaseService
from src.dishes.models import Dish
from src.dishes.schemas import DishCreate, DishUpdate
from src.dishes.validators import check_exists_cafes_ids


class CRUDDish(DatabaseService[Dish, DishCreate, DishUpdate]):
    """CRUD для блюд."""

    async def get_dishes(
        self,
        cafe_id: Optional[int],
        session: AsyncSession,
        show_all: bool = False,
    ) -> List[Dish]:
        """Получение списка блюд.

        По умолчанию выдача только dish.is_active=True.
        Если указан cafe_id — фильтруем блюда, относящиеся к этому кафе.
        """
        stmt = select(Dish)
        if not show_all:
            stmt = stmt.where(Dish.is_active.is_(True))
        if cafe_id:
            stmt = stmt.join(Dish.cafes).where(Cafe.id == cafe_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_dish(
        self,
        session: AsyncSession,
        obj_in: DishCreate,
    ) -> Dish:
        """Создание блюда с учётом id кафе."""
        data = obj_in.model_dump(exclude_unset=True)
        cafes_id: List[int] = data.pop('cafes_id', None)
        await check_exists_cafes_ids(cafes_id, session=session)
        cafes = await self.get_related_objects(
            session=session,
            field_name='dishes',
            ids=cafes_id,
            model=Cafe,
            required=True,
        )

        db_obj = await self.create(
            obj_in, session, related={'cafes': cafes},
        )
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update_dish(
        self,
        session: AsyncSession,
        db_obj: Dish,
        obj_in: DishUpdate,
    ) -> Dish:
        """Обновление блюда."""
        update_data = obj_in.model_dump(exclude_unset=True)
        cafes_id = update_data.pop('cafes_id', None)

        cafes = await self.get_related_objects(
            session=session,
            field_name='dishes',
            ids=cafes_id,
            model=Cafe,
            required=True,
        )

        db_obj = await self.update(
            db_obj=db_obj,
            obj_in=obj_in,
            session=session,
            related={'cafes': cafes},
        )

        await session.commit()
        await session.refresh(db_obj)
        return db_obj


crud_dish = CRUDDish(Dish)
