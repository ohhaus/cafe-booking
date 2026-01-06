# src/dishes/views.py
import logging
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)
from src.database.sessions import get_async_session
from src.dishes.schemas import DishCreate, DishInfo, DishUpdate
from src.dishes.services import dishes_service, get_dish_by_dish_id, get_dishes
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()
logger = logging.getLogger('app')


@router.get(
    '/',
    response_model=List[DishInfo],
    summary='Получение списка блюд',
    description=(
        'Получение списка блюд. '
        'Для администраторов и менеджеров - '
        'все блюда (с возможностью выбора),'
        ' для пользователей - только активные.'
    ),
    responses=list_responses(),
)
async def get_all_dishes(
    show_all: bool = Query(
        False,
        title='Показывать все блюда?',
        description='Показывать все блюда или нет. '
        'По умолчанию показывает все блюда',
    ),
    cafe_id: Optional[UUID] = Query(
        None,
        title='Cafe Id',
        description='ID кафе, в котором показывать блюда. '
        'Если не задано - показывает все блюда во всех кафе',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> list[DishInfo]:
    """Получение списка блюд с возможностью фильтрации."""
    return await get_dishes(
        session=session,
        current_user=current_user,
        show_all=show_all,
        cafe_id=cafe_id,
    )


@router.post(
    '/',
    response_model=DishInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового блюда',
    description=(
        'Cоздает новое блюда. Только для администраторов и менеджеров.'
    ),
    responses=create_responses(DishInfo),
)
async def create_dish_new(
    dish_in: DishCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> DishInfo:
    """Создание нового блюда."""
    dish = await dishes_service.create_dish_service(
        session=session, dish_in=dish_in, current_user=current_user
    )
    return DishInfo.model_validate(dish)


@router.get(
    '/{dish_id}',
    response_model=DishInfo,
    summary='Получение информации о блюде по его ID',
    description=(
        'Получение информации о блюде по его ID. '
        'Для администраторов и менеджеров - все блюда, '
        'для пользователей - только активные.'
    ),
    responses=retrieve_responses(),
)
async def get_dish_by_id(
    dish_id: Annotated[UUID, Path(title='ID блюда')],
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Получение информации о блюде по его ID."""
    return await get_dish_by_dish_id(
        session=session,
        dish_id=dish_id,
        current_user=current_user,
    )


@router.patch(
    '/{dish_id}',
    response_model=DishInfo,
    summary='Обновление информации о блюде по его ID',
    description='Обновление информации о блюде по его ID. '
    'Только для администраторов и менеджеров.',
    responses=retrieve_responses(),
)
async def update_dish(
    dish_id: UUID,
    dish_update: DishUpdate,
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Обновление информации о блюде по его ID."""
    return await dishes_service.update_dish_service(
        session=session,
        dish_id=dish_id,
        dish_update=dish_update,
        current_user=current_user,
    )
