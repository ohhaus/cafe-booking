from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.models import Action, action_cafe
from src.actions.schemas import ActionCreate, ActionUpdate
from src.actions.validators import (
    check_action_name_unique,
    check_exists_action,
)
from src.cafes.models import Cafe
from src.database.service import DatabaseService


class ActionService(DatabaseService[Action, ActionCreate, ActionUpdate]):
    """Сервис для работы с акциями."""

    async def create_action(
        self,
        session: AsyncSession,
        obj_in: ActionCreate,
    ) -> Action:
        """Создание новой акции.

        Если указаны cafes_id, связывает акцию с кафе.
        """
        # Проверяем уникальность названия
        await check_action_name_unique(obj_in.name, session)

        data = obj_in.model_dump(exclude_unset=True)
        cafes_id = data.pop('cafes_id', None)

        if cafes_id:
            cafes_id = list(dict.fromkeys(cafes_id))

        db_obj = Action(**data)

        try:
            if cafes_id:
                res = await session.execute(
                    select(Cafe).where(Cafe.id.in_(cafes_id)),
                )
                cafes_list = list(res.scalars().all())

                found_ids = {cafe.id for cafe in cafes_list}
                missing = [cid for cid in cafes_id if cid not in found_ids]
                if missing:
                    raise ValueError(f'Не найдены кафе с id: {missing}')

                db_obj.cafes = cafes_list

            session.add(db_obj)
            await session.commit()

        except IntegrityError:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise

        await session.refresh(db_obj, attribute_names=['cafes'])
        return db_obj

    async def update_action(
        self,
        session: AsyncSession,
        db_obj: Action,
        obj_in: ActionUpdate,
    ) -> Action:
        """Обновление акции."""
        # Проверяем уникальность названия (если оно изменяется)
        if obj_in.name is not None and obj_in.name != db_obj.name:
            await check_action_name_unique(
                obj_in.name,
                session,
                exclude_id=db_obj.id,
            )

        update_data = obj_in.model_dump(exclude_unset=True)
        cafes_id = update_data.pop('cafes_id', None)

        # Если переданы кафе - обновляем связь
        if cafes_id is not None:
            res = await session.execute(
                select(Cafe).where(Cafe.id.in_(cafes_id)),
            )
            cafes_list = list(res.scalars().all())

            found_ids = {cafe.id for cafe in cafes_list}
            missing = [cid for cid in cafes_id if cid not in found_ids]
            if missing:
                raise ValueError(f'Не найдены кафе с id: {missing}')

            db_obj.cafes = cafes_list

        # Обновляем остальные поля
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await session.commit()
        await session.refresh(db_obj, attribute_names=['cafes'])
        return db_obj

    async def get_related_cafes(
        self,
        session: AsyncSession,
        action_id: UUID,
    ) -> List[Cafe]:
        """Получает связанные активные кафе для данной акции.

        Args:
            session: Сессия БД
            action_id: UUID акции

        Returns:
            Список объектов Cafe

        """
        # Проверяем, что акция существует
        await check_exists_action(action_id, session)

        # Получаем кафе через таблицу связи
        query = (
            select(Cafe)
            .join(action_cafe)
            .where(
                action_cafe.c.action_id == action_id,
                Cafe.active.is_(True),
            )
        )
        result = await session.execute(query)
        return list(result.scalars().all())


action_service = ActionService(Action)
