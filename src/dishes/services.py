# src/dishes/services.py

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.database.service import DatabaseService
from src.dishes.models import Dish, dish_cafe
from src.dishes.schemas import DishCreate, DishUpdate
from src.dishes.validators import check_exists_dish


class DishService(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Сервис для работы с блюдами."""

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

                db_obj.cafes = cafes_list

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
        """Получает связанные активные кафе для данного блюда.

        Args:
            session: Сессия БД
            dish_id: UUID блюда

        Returns:
            Список объектов Cafe

        Raises:
            NotFoundException: Если блюдо не найдено

        """
        # Сначала проверяем, что блюдо существует
        await check_exists_dish(dish_id, session)

        # Получаем кафе через таблицу связи
        query = (
            select(Cafe)
            .join(dish_cafe)
            .where(
                dish_cafe.c.dish_id == dish_id,
                Cafe.active.is_(True),
            )
        )
        result = await session.execute(query)
        return result.scalars().all()


dish_service = DishService(Dish)
