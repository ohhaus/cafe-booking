import logging
from http import HTTPStatus
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.sessions import get_async_session
from src.dishes.crud import crud_dish
from src.dishes.responses import (
    DISH_CREATE_RESPONSES,
    DISH_GET_RESPONSES,
    DISH_RESPONSES,
    DISH_UPDATE_RESPONSES,
)
from src.dishes.schemas import DishCreate, DishInfo, DishUpdate
from src.dishes.validators import check_exists_cafes_ids, check_exists_dish
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter(
    prefix='/dishes',
    tags=['Блюда'],
)


logger = logging.getLogger('app')


@router.get('/', response_model=List[DishInfo], responses=DISH_RESPONSES)
async def get_dishes(
    cafe_id: Optional[int],
    show_all: bool = False,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> List[DishInfo]:
    """Получение списка блюд."""
    if show_all:
        if current_user.role not in (Roles.MANAGER, Roles.ADMIN):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail='Недостаточно прав',
            )
        if cafe_id is not None:
            await can_manage_cafe(cafe_id, session, current_user)
    return await crud_dish.get_dishes(
        session=session,
        show_all=show_all,
        cafe_id=cafe_id,
    )


@router.get(
    '/{dish_id}',
    response_model=DishInfo,
    responses=DISH_GET_RESPONSES,
    dependencies=[Depends(get_current_user)],
)
async def get_dish(
    dish_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> Optional[DishInfo]:
    """Получение одного блюда."""
    return await check_exists_dish(dish_id=dish_id, session=session)


@router.post(
    '/',
    response_model=DishInfo,
    status_code=status.HTTP_201_CREATED,
    responses=DISH_CREATE_RESPONSES,
)
async def create_dish(
    dish_in: DishCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.MANAGER, UserRole.ADMIN],
        ),
    ),
) -> DishInfo:
    """Создание блюда."""
    await check_exists_cafes_ids(dish_in.cafes_id, session)
    for cafe_id in dish_in.cafes_id:
        await can_manage_cafe(cafe_id, session, current_user)
    dish = await crud_dish.create_dish(session=session, obj_in=dish_in)
    await session.commit()
    await session.refresh(dish)
    return DishInfo.model_validate(dish, from_attributes=True)


@router.patch(
    '/{dish_id}',
    response_model=DishInfo,
    responses=DISH_UPDATE_RESPONSES,
)
async def update_dish(
    dish_id: int,
    dish_in: DishUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.MANAGER, UserRole.ADMIN],
        ),
    ),
) -> DishInfo:
    """Частичное обновление блюда."""
    await check_exists_cafes_ids(dish_in.cafes_id, session)
    for cafe_id in dish_in.cafes_id:
        await can_manage_cafe(cafe_id, session, current_user)
    dish = await check_exists_dish(dish_id=dish_id, session=session)
    updated_dish = await crud_dish.update(
        session=session,
        db_obj=dish,
        obj_in=dish_in,
    )
    await session.commit()
    return updated_dish
