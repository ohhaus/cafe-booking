from typing import Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, and_, or_, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud_base import CRUDBase
from src.cafes.models import Cafe, cafes_managers
from src.cafes.schemas import CafeCreate, CafeUpdate, CafeOut


class CRUDCafe(CRUDBase):
    """CRUD для модели Cafe."""

    async def create(
        self,
        obj_in: CafeCreate,
        session: AsyncSession,
    ) -> CafeOut:
        """Создает новый объект кафе, на основе входных данных."""
        data = jsonable_encoder(
            obj_in,
            exclude={'managers'},
        )
        cafe = Cafe(**data)
        session.add(cafe)

        await session.flush()

        if obj_in.manager_ids:
            values = [
                {'cafe_id': cafe.id, 'user_id': manager_id}
                for manager_id in obj_in.manager_ids
            ]
            await session.execute(insert(cafes_managers), values)

        await session.commit()
        await session.refresh(cafe)

        return cafe

    async def update(
        self,
        db_obj: Cafe,
        obj_in: CafeUpdate,
        session: AsyncSession,
    ) -> Cafe:
        """Обновляет объект кафе и его менеджеров."""
        update_data = obj_in.model_dump(awclude_unset=True)
        manager_ids = update_data.pop('manager_ids', None)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        session.add(db_obj)
        await session.flush()

        if manager_ids is not None:
            await session.execute(
                delete(cafes_managers).where(
                    cafes_managers.c.cafe_id == db_obj.id
                )
            )
            if manager_ids:
                values = [
                    {'cafe_id': db_obj.id, 'user_id': manager_id}
                    for manager_id in manager_ids
                ]
                await session.execute(insert(cafes_managers), values)

        await session.commit()
        await session.refresh(db_obj)

        return db_obj
