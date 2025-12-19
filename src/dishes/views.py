import logging

# from http import HTTPStatus
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DatabaseError  # IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.sessions import get_async_session
from src.dishes.crud import crud_dish
from src.dishes.responses import (
    # DISH_CREATE_RESPONSES,
    # DISH_GET_RESPONSES,
    DISH_GET_RESPONSES,
    # DISH_UPDATE_RESPONSES,
)
from src.dishes.schemas import DishInfo  # DishCreate, DishUpdate
from src.users.dependencies import require_roles
from src.users.models import User  # UserRole


# from src.dishes.validators import check_exists_cafes_ids, check_exists_dish


router = APIRouter(
    prefix='/dishes',
    tags=['Блюда'],
)


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
    try:
        crud = crud_dish(session)
        is_staff = current_user.is_staff()

        dishes = await crud.get_dishes(
            current_user_id=current_user.id,
            is_staff=is_staff,
            show_all=(show_all if is_staff else False),
            cafe_id=cafe_id,
        )

        if not dishes:
            logger.info('Нет блюд для кафе %s',
                        str(cafe_id) if cafe_id else 'всех кафе')

        logger.info(
            'Найдено %d блюд для кафе %s',
            len(dishes),
            str(cafe_id) if cafe_id else 'всех кафе',
        )

        return [DishInfo.model_validate(b) for b in dishes]

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении блюд: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении списка блюд: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


# @router.get(
#     '/{dish_id}',
#     response_model=DishInfo,
#     responses=DISH_GET_RESPONSES,
#     dependencies=[Depends(get_current_user)],
# )
# async def get_dish(
#     dish_id: int,
#     session: AsyncSession = Depends(get_async_session),
# ) -> Optional[DishInfo]:
#     """Получение одного блюда."""
#     return await check_exists_dish(dish_id=dish_id, session=session)


# @router.post(
#     '/',
#     response_model=DishInfo,
#     status_code=status.HTTP_201_CREATED,
#     responses=DISH_CREATE_RESPONSES,
# )
# async def create_dish(
#     dish_in: DishCreate,
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(
#         require_roles(
#             allowed_roles=[UserRole.MANAGER, UserRole.ADMIN],
#         ),
#     ),
# ) -> DishInfo:
#     """Создание блюда."""
#     await check_exists_cafes_ids(dish_in.cafes_id, session)
#     for cafe_id in dish_in.cafes_id:
#         await can_manage_cafe(cafe_id, session, current_user)
#     dish = await crud_dish.create_dish(session=session, obj_in=dish_in)
#     await session.commit()
#     await session.refresh(dish)
#     return DishInfo.model_validate(dish, from_attributes=True)


# @router.patch(
#     '/{dish_id}',
#     response_model=DishInfo,
#     responses=DISH_UPDATE_RESPONSES,
# )
# async def update_dish(
#     dish_id: int,
#     dish_in: DishUpdate,
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(
#         require_roles(
#             allowed_roles=[UserRole.MANAGER, UserRole.ADMIN],
#         ),
#     ),
# ) -> DishInfo:
#     """Частичное обновление блюда."""
#     await check_exists_cafes_ids(dish_in.cafes_id, session)
#     for cafe_id in dish_in.cafes_id:
#         await can_manage_cafe(cafe_id, session, current_user)
#     dish = await check_exists_dish(dish_id=dish_id, session=session)
#     updated_dish = await crud_dish.update(
#         session=session,
#         db_obj=dish,
#         obj_in=dish_in,
#     )
#     await session.commit()
#     return updated_dish
