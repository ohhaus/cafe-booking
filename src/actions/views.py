import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.actions.models import Action
from src.actions.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.actions.schemas import ActionCreate, ActionInfo, ActionUpdate
from src.actions.service import action_service
from src.actions.validators import (
    check_action_name_unique,
    check_exists_cafes_ids,
)
from src.cafes.models import Cafe
from src.common.exceptions import NotFoundException, ValidationErrorException
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()
logger = logging.getLogger('app')


@router.get(
    '/',
    response_model=List[ActionInfo],
    summary='Получение списка акций',
    description=(
        'Получение списка акций. '
        'Для администраторов и менеджеров - '
        'все акции (с возможностью выбора),'
        ' для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,  # type: ignore[arg-type]
)
async def get_all_actions(
    show_all: bool = False,
    cafe_id: UUID | None = None,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> list[ActionInfo]:
    """Получение списка акций с возможностью фильтрации."""
    logger.info(
        'Пользователь %s запросил все акции с фильтрами: '
        'show_all=%s, cafe_id=%s',
        current_user.id,
        show_all,
        cafe_id,
        extra={'user_id': str(current_user.id)},
    )

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
        return [
            ActionInfo.model_validate(a, from_attributes=True) for a in actions
        ]
    except ValidationError:
        logger.error(
            'Ошибка валидации данных акций',
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise ValidationErrorException(
            'Ошибка валидации данных акции',
        )


@router.post(
    '/',
    response_model=ActionInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание новой акции',
    description=(
        'Создает новую акцию. Только для администраторов и менеджеров.'
    ),
    responses=CREATE_RESPONSES,  # type: ignore[arg-type]
)
async def create_action(
    action_in: ActionCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> ActionInfo:
    """Создание новой акции."""
    logger.info(
        'Пользователь %s инициировал создание акции %s',
        current_user.id,
        action_in.name,
        extra={'user_id': str(current_user.id)},
    )

    # Проверка существования кафе
    await check_exists_cafes_ids(action_in.cafes_id, session)

    # Логика создания акции
    try:
        new_action = await action_service.create_action(
            session=session,
            obj_in=action_in,
        )
        return ActionInfo.model_validate(new_action)

    except ValueError as e:
        logger.warning(
            'Ошибка валидации при создании акции: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.critical(
            'Ошибка при создании акции: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Ошибка при создании акции.',
        ) from e


@router.get(
    '/{action_id}',
    response_model=ActionInfo,
    summary='Получение информации об акции по её ID',
    description=(
        'Получение информации об акции по её ID. '
        'Для администраторов и менеджеров - все акции, '
        'для пользователей - только активные.'
    ),
    responses=GET_BY_ID_RESPONSES,  # type: ignore[arg-type]
)
async def get_action_by_id(
    action_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> ActionInfo:
    """Получение информации об акции по её ID."""
    logger.info(
        'Пользователь %s запросил информацию об акции с ID: %s',
        current_user.id,
        action_id,
        extra={'user_id': str(current_user.id)},
    )

    # Определяем, может ли пользователь видеть все акции
    can_view_all = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)

    # Формируем фильтры
    filters = [Action.id == action_id]
    if not can_view_all:
        filters.append(Action.active.is_(True))

    # Получаем акцию из БД
    actions = await action_service.get_multi(
        session=session,
        filters=filters,
        relationships=['cafes'],
    )

    action = actions[0] if actions else None

    if action is None:
        logger.warning(
            'Акция с ID: %s не найдена для пользователя %s',
            action_id,
            current_user.id,
            extra={'user_id': str(current_user.id)},
        )
        raise NotFoundException(message='Акция не найдена')

    logger.info(
        'Акция с ID: %s успешно получена для пользователя %s',
        action_id,
        current_user.id,
        extra={'user_id': str(current_user.id)},
    )

    return ActionInfo.model_validate(action, from_attributes=True)


@router.patch(
    '/{action_id}',
    response_model=ActionInfo,
    summary='Обновление информации об акции по её ID',
    description='Обновление информации об акции по её ID. '
    'Только для администраторов и менеджеров.',
    responses=GET_BY_ID_RESPONSES,  # type: ignore[arg-type]
)
async def update_action(
    action_id: UUID,
    action_update: ActionUpdate,
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
    session: AsyncSession = Depends(get_async_session),
) -> ActionInfo:
    """Обновление информации об акции по её ID."""
    logger.info(
        'Пользователь %s инициировал обновление акции с ID: %s',
        current_user.id,
        action_id,
        extra={'user_id': str(current_user.id)},
    )

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
    if action_update.name and action_update.name != action.name:
        await check_action_name_unique(
            action_update.name,
            session,
            exclude_id=action_id,
        )

    # Проверяем существование кафе (если они переданы)
    if action_update.cafes_id:
        await check_exists_cafes_ids(action_update.cafes_id, session)

    # Обновляем акцию
    try:
        updated_action = await action_service.update_action(
            session=session,
            db_obj=action,
            obj_in=action_update,
        )
        logger.info(
            'Акция с ID: %s успешно обновлена пользователем %s',
            action_id,
            current_user.id,
            extra={'user_id': str(current_user.id)},
        )
        return ActionInfo.model_validate(updated_action, from_attributes=True)

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


@router.delete(
    '/{action_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление акции по ID',
    description='Удаление акции по ID. Только для администраторов.',
)
async def delete_action(
    action_id: UUID,
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Удаление акции по ID."""
    logger.info(
        'Пользователь %s инициировал удаление акции с ID: %s',
        current_user.id,
        action_id,
        extra={'user_id': str(current_user.id)},
    )

    # Получаем акцию
    stmt = select(Action).where(Action.id == action_id)
    result = await session.execute(stmt)
    action = result.scalar_one_or_none()

    if not action:
        logger.warning(
            'Акция с ID: %s не найдена для удаления',
            action_id,
            extra={'user_id': str(current_user.id)},
        )
        raise NotFoundException

    # Удаляем акцию
    await session.delete(action)
    await session.commit()

    logger.info(
        'Акция с ID: %s успешно удалена пользователем %s',
        action_id,
        current_user.id,
        extra={'user_id': str(current_user.id)},
    )
