# src/dishes/views.py
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Sequence, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cafes.models import Cafe
from src.common.logging.decorators import log_action
from src.database.sessions import get_async_session
from src.dishes.crud import crud_dish
from src.dishes.models import Dish
from src.dishes.responses import (
    DISH_CREATE_RESPONSES,
    DISH_GET_BY_ID_RESPONSES,
    DISH_GET_RESPONSES,
)
from src.dishes.schemas import DishCreate, DishInfo, DishUpdate
from src.dishes.services import dish_service
from src.dishes.validators import check_exists_cafes_ids
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()
logger = logging.getLogger('app')


@router.get(
    '/test_get_all_dishes',
    response_model=List[DishInfo],
    summary='Получение списка блюд',
    description=(
        'Получение списка блюд. '
        'Для администраторов и менеджеров - '
        'все блюда (с возможностью выбора),'
        ' для пользователей - только активные.'
        ),
    responses=DISH_GET_RESPONSES,
)
async def get_all_dishes(
    show_all: bool = False,
    cafe_id: int | None = None,
    current_user: User | None = Depends(
        require_roles(
            [UserRole.MANAGER, UserRole.ADMIN],
            allow_guest=True,
        ),
    ),
    session: AsyncSession = Depends(get_async_session)
) -> list[DishInfo]:
    """Получает все блюда."""
    dishes = await dish_service.get_multi(
        session=session,
        relationships=["cafes"]
    )

    return [
        DishInfo.model_validate(dish, from_attributes=True)
        for dish in dishes
    ]


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
    responses=DISH_GET_RESPONSES,
)
async def get_dishes(
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
) -> List[DishInfo]:
    """Получение списка блюд."""
    stmt = select(Dish).options(selectinload(Dish.cafes))

    if cafe_id is not None:
        stmt = stmt.join(Dish.cafes).where(Cafe.id == cafe_id)

    is_staff = current_user.is_staff()

    if is_staff:
        if not show_all:
            stmt = stmt.where(Dish.active.is_(True))
    else:
        stmt = stmt.where(Dish.active.is_(True))

    result = await session.execute(stmt)

    return result.scalars().unique().all()


@router.post(
    '/',
    response_model=DishInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового блюда',
    description=(
        'Cоздает новое блюда. Только для администраторов и менеджеров.'
    ),
    responses=DISH_CREATE_RESPONSES,
)
async def create_dish(
    dish_in: DishCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_roles(allow_guest=False)),
) -> DishInfo:
    """Создание нового блюда."""
    logger.info(
        'Пользователь %s инициировал создание блюда %s',
        current_user.id,
        dish_in.name,
        extra={'user_id': str(current_user.id)},
    )

    # Проверка существования кафе
    await check_exists_cafes_ids(dish_in.cafes_id, session)

    # Логика создания блюда
    try:
        new_dish = await crud_dish.create_dish(session=session, obj_in=dish_in)
        return DishInfo.model_validate(new_dish)

    except Exception as e:
        logger.critical(
            'Ошибка при создании блюда: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Ошибка при создании блюда.',
        ) from e


@router.get(
    '/{dish_id}',
    response_model=DishInfo,
    summary='Получение информации о блюде по его ID',
    description=(
        'Получение информации о блюде по его ID. '
        'Для администраторов и менеджеров - все блюда, '
        'для пользователей - только активные.'
    ),
    responses=DISH_GET_BY_ID_RESPONSES,
)
async def get_dish_by_id(
    dish_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Получение информации о блюде по его ID."""
    stmt = (
        select(Dish)
        .where(Dish.id == dish_id)
        .options(selectinload(Dish.cafes))
    )

    is_staff = current_user.is_staff()

    if not is_staff:
        stmt = stmt.where(Dish.active.is_(True))

    result = await session.execute(stmt)
    dish = result.scalar_one_or_none()

    if dish is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dish not found",
        )

    return dish


@router.patch(
    '/{dish_id}',
    response_model=DishInfo,
    summary='Обновление информации о блюде по его ID',
    description='Обновление информации о блюде по его ID. '
    'Только для администраторов и менеджеров.',
    responses=DISH_GET_BY_ID_RESPONSES,
)
async def update_dish(
    dish_id: UUID,
    dish_update: DishUpdate,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Обновление информации о блюде по его ID."""
    # Загружаем блюдо с предварительной загрузкой отношения cafes
    stmt = select(
        Dish,
        ).where(Dish.id == dish_id).options(selectinload(Dish.cafes))
    result = await session.execute(stmt)
    dish = result.scalar_one_or_none()

    if not dish:
        raise HTTPException(
            status_code=404,
            message="Dish not found")

    # Обновляем данные
    for key, value in dish_update.dict(exclude_unset=True).items():
        setattr(dish, key, value)

    await session.commit()
    await session.refresh(dish)

    return dish
