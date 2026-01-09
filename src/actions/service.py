import logging
from typing import List
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.actions.models import Action
from src.actions.schemas import ActionCreate, ActionInfo, ActionUpdate
from src.actions.validators import (
    check_action_name_unique,
    check_exists_cafes_ids,
)
from src.cafes.models import Cafe
from src.common.exceptions import NotFoundException, ValidationErrorException
from src.database.service import DatabaseService
from src.users.models import User, UserRole


logger = logging.getLogger('app')


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
        # Проверка существования кафе
        await check_exists_cafes_ids(obj_in.cafes_id, session)

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
        action_id: UUID,
        current_user: User,
        obj_in: ActionUpdate,
    ) -> Action:
        """Обновление акции."""
        # Получаем акцию с загруженными кафе
        stmt = (
            select(Action)
            .where(Action.id == action_id)
            .options(selectinload(Action.cafes))
        )
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()

        if not action:
            logger.warning(
                'Акция с ID: %s не найдена для обновления',
                action_id,
                extra={'user_id': str(current_user.id)},
            )
            raise NotFoundException

        # Проверяем уникальность названия (если оно изменяется)
        if obj_in.name and obj_in.name != action.name:
            await check_action_name_unique(
                obj_in.name,
                session,
                exclude_id=action_id,
            )

        # Проверяем существование кафе (если они переданы)
        if obj_in.cafes_id:
            await check_exists_cafes_ids(obj_in.cafes_id, session)

        # Обновляем акцию
        try:
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

                action.cafes = cafes_list

            # Обновляем остальные поля
            for field, value in update_data.items():
                if hasattr(action, field):
                    setattr(action, field, value)

            await session.commit()
            await session.refresh(action, attribute_names=['cafes'])
            return action

        except ValueError as e:
            logger.warning(
                'Ошибка валидации при обновлении акции %s: %s',
                action_id,
                str(e),
                extra={'user_id': str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.critical(
                'Ошибка при обновлении акции %s: %s',
                action_id,
                str(e),
                extra={'user_id': str(current_user.id)},
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Ошибка при обновлении акции.',
            ) from e

    async def get_actions_with_cafes(
        self,
        session: AsyncSession,
        current_user: User,
        show_all: bool = False,
        cafe_id: UUID | None = None,
    ) -> List[ActionInfo]:
        """Получает список акций со связанными кафе."""
        can_view_all = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)

        # Вместо фильтров используем прямой запрос
        if cafe_id is not None:
            # Если нужна фильтрация по cafe_id, делаем специальный запрос
            query = select(Action).join(Action.cafes).where(Cafe.id == cafe_id)

            if not (can_view_all and show_all):
                query = query.where(Action.active.is_(True))

            result = await session.execute(query)
            actions = list(result.scalars().unique().all())
        else:
            # Обычный запрос без фильтрации по кафе
            filters = []
            if not (can_view_all and show_all):
                filters.append(Action.active.is_(True))

            actions = await action_service.get_multi(
                session=session,
                filters=filters,
                relationships=['cafes'],
            )

        if not actions:
            logger.info(
                'Для пользователя %s не найдено акций с фильтрами: '
                'show_all=%s, cafe_id=%s',
                current_user.id,
                show_all,
                cafe_id,
                extra={'user_id': str(current_user.id)},
            )
            raise NotFoundException

        # Валидация и преобразование
        try:
            return actions

        except ValidationError:
            logger.error(
                'Ошибка валидации данных акций',
                extra={'user_id': str(current_user.id)},
                exc_info=True,
            )
            raise ValidationErrorException(
                'Ошибка валидации данных акции',
            )

    async def get_action_by_id(
        self,
        session: AsyncSession,
        current_user: User,
        action_id: UUID,
    ) -> Action:
        """Получает данные акции со связанными кафе."""
        # Определяем, может ли пользователь видеть все акции
        can_view_all = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)

        # Формируем фильтры
        filters = [Action.id == action_id]
        if not can_view_all:
            filters.append(Action.active.is_(True))

        # Получаем акцию из БД
        action = await action_service.get(
            session=session,
            id=action_id,
        )

        if action is None:
            logger.warning(
                'Акция с ID: %s не найдена для пользователя %s',
                action_id,
                current_user.id,
                extra={'user_id': str(current_user.id)},
            )
            raise NotFoundException(message='Акция не найдена')

        return action


action_service = ActionService(Action)
