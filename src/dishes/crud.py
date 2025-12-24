from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.database.service import DatabaseService
from src.dishes.models import Dish, dish_cafe
from src.dishes.schemas import DishCreate, DishUpdate


class CRUDDish(DatabaseService[Dish, DishCreate, DishUpdate]):
    """CRUD для блюд."""

    async def get_dishes(
        self,
        cafe_id: Optional[UUID],
        session: AsyncSession,
        show_all: bool = False,
    ) -> List[Dish]:
        """Получение списка блюд.

        По умолчанию выдача только dish.is_active=True.
        Если указан cafe_id — фильтруем блюда, относящиеся к этому кафе.
        """
        stmt = select(Dish)
        if not show_all:
            stmt = stmt.where(Dish.active.is_(True))
        if cafe_id:
            stmt = stmt.join(Dish.cafes).where(Cafe.id == cafe_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_dish(
            self, session: AsyncSession,
            obj_in: DishCreate,
            ) -> Dish:
        """Создание нового блюда.

        Если указаны cafes_id, связывает блюдо с кафе.
        """
        data = obj_in.model_dump(exclude_unset=True)
        cafes_id = data.pop("cafes_id", None)

        if cafes_id:
            cafes_id = list(dict.fromkeys(cafes_id))

        db_obj = Dish(**data)

        try:
            if cafes_id:
                res = await session.execute(
                    select(Cafe).where(Cafe.id.in_(cafes_id)),
                    )
                cafes_list = res.scalars().all()

                found_ids = {c.id for c in cafes_list}
                missing = [cid for cid in cafes_id if cid not in found_ids]
                if missing:
                    raise ValueError(f"Не найдены кафе с id: {missing}")

                db_obj.cafes = cafes_list   # назначаем ДО add()

            session.add(db_obj)
            await session.commit()

        except IntegrityError:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise

        await session.refresh(db_obj, attribute_names=["cafes"])
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
            field_name='dishes ',
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

    async def get_related_objects(
            self,
            session: AsyncSession,
            dish_id: UUID,
            ) -> List[Cafe]:
        """Получает связанные кафе для данного блюда."""
        query = (
            select(Cafe)
            .join(dish_cafe)
            .filter(dish_cafe.c.dish_id == dish_id)
        )
        result = await session.execute(query)
        return result.scalars().all()


crud_dish = CRUDDish(Dish)
