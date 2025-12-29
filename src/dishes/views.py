# src/dishes/views.py
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cafes.models import Cafe
from src.common.exceptions import NotFoundException, ValidationErrorException
from src.database.sessions import get_async_session
from src.dishes.models import Dish
from src.dishes.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.dishes.schemas import DishCreate, DishInfo, DishUpdate
from src.dishes.services import dish_service
from src.dishes.validators import check_exists_cafes_ids, check_exists_dish
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
    responses=GET_RESPONSES,
)
async def get_all_dishes(
    show_all: bool = False,
    cafe_id: UUID | None = None,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> list[DishInfo]:
    """Получение списка блюд с возможностью фильтрации."""
    logger.info(
        'Пользователь %s запросил все блюда с фильтрами: '
        'show_all=%s, cafe_id=%s',
        current_user.id, show_all, cafe_id,
        extra={'user_id': str(current_user.id)},
    )

    can_view_all = False

    if current_user.role in (UserRole.ADMIN, UserRole.MANAGER):
        can_view_all = True

    filters = []

    if not (can_view_all and show_all):
        filters.append(Dish.active.is_(True))

    if cafe_id is not None:
        filters.append(Dish.cafes.any(Cafe.id == cafe_id))

    dishes = await dish_service.get_multi(
        session=session,
        filters=filters,
        relationships=["cafes"],
    )

    if dishes is None:
        raise NotFoundException

    try:
        return [
            DishInfo.model_validate(d, from_attributes=True) for d in dishes
            ]
    except ValidationError as e:
        logger.error(
            'Ошибка валидации данных блюд',
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise ValidationErrorException(
            f'Ошибка валидации данных блюда c ID: {d.id}'
            )


@router.post(
    '/',
    response_model=DishInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового блюда',
    description=(
        'Cоздает новое блюда. Только для администраторов и менеджеров.'
    ),
    responses=CREATE_RESPONSES,
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
        new_dish = await dish_service.create_dish(
            session=session,
            obj_in=dish_in,
            )
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
    responses=GET_BY_ID_RESPONSES,
)
async def get_dish_by_id(
    dish_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Получение информации о блюде по его ID."""
    logger.info(
        'Пользователь %s запросил информацию о блюде с ID: %s',
        current_user.id,
        dish_id,
        extra={'user_id': str(current_user.id)},
        )

    if not check_exists_dish(dish_id=dish_id, session=session):
        logger.info(
            'Блюда с ID: %s не существует',
            dish_id,
            extra={'user_id': str(current_user.id)},
            )
        raise NotFoundException
    logger.info(
        'Блюда с ID: %s все таки получается существует',
        dish_id,
        extra={'user_id': str(current_user.id)},
        )
    raise NotFoundException

    can_view_all = (
        current_user is not None
        and current_user.role in (UserRole.ADMIN, UserRole.MANAGER)
    )

    filters = [Dish.id == dish_id]

    if not can_view_all:
        filters.append(Dish.active.is_(True))

    dishes = await dish_service.get_multi(
        session=session,
        filters=filters,
        relationships=['cafes'],
    )

    dish = dishes[0] if dishes else None

    return DishInfo.model_validate(dish, from_attributes=True)


@router.patch(
    '/{dish_id}',
    response_model=DishInfo,
    summary='Обновление информации о блюде по его ID',
    description='Обновление информации о блюде по его ID. '
    'Только для администраторов и менеджеров.',
    responses=GET_BY_ID_RESPONSES,
)
async def update_dish(
    dish_id: UUID,
    dish_update: DishUpdate,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Обновление информации о блюде по его ID."""
    stmt = (
        select(
            Dish,
        )
        .where(Dish.id == dish_id)
        .options(selectinload(Dish.cafes))
    )
    result = await session.execute(stmt)
    dish = result.scalar_one_or_none()

    if not dish:
        raise NotFoundException

    # Обновляем данные
    for key, value in dish_update.dict(exclude_unset=True).items():
        setattr(dish, key, value)

    await session.commit()
    await session.refresh(dish)

    return dish
