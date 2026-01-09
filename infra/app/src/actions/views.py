import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.actions.schemas import ActionCreate, ActionInfo, ActionUpdate
from src.actions.service import action_service
from src.common.logging import log_action
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
@log_action('Запрос на получение списка акций.')
async def get_all_actions(
    show_all: bool = False,
    cafe_id: UUID | None = None,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> list[ActionInfo]:
    """Получение списка акций с возможностью фильтрации."""
    actions = await action_service.get_actions_with_cafes(
        session=session,
        current_user=current_user,
        show_all=show_all,
        cafe_id=cafe_id,
    )

    return [
        ActionInfo.model_validate(action, from_attributes=True)
        for action in actions
    ]


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
@log_action('Запрос на создание новой акции.')
async def create_action(
    action_in: ActionCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> ActionInfo:
    """Создание новой акции."""
    new_action = await action_service.create_action(
        session=session,
        obj_in=action_in,
    )
    return ActionInfo.model_validate(new_action)


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
@log_action('Запрос на получение акции по ID.')
async def get_action_by_id(
    action_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> ActionInfo:
    """Получение информации об акции по её ID."""
    action = await action_service.get_action_by_id(
        session=session,
        action_id=action_id,
        current_user=current_user,
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
@log_action('Запрос на обновление акции.')
async def update_action(
    action_id: UUID,
    action_update: ActionUpdate,
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
    session: AsyncSession = Depends(get_async_session),
) -> ActionInfo:
    """Обновление информации об акции по её ID."""
    updated_action = await action_service.update_action(
        session=session,
        action_id=action_id,
        current_user=current_user,
        obj_in=action_update,
    )
    return ActionInfo.model_validate(updated_action, from_attributes=True)
