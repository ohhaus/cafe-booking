import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DatabaseError  # IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.sessions import get_async_session
from src.dishes.crud import crud_dish
from src.dishes.responses import (
    DISH_CREATE_RESPONSES,
    DISH_GET_RESPONSES,
    # DISH_UPDATE_RESPONSES,
)
from src.dishes.schemas import DishCreate, DishInfo  # DishUpdate
from src.dishes.validators import check_exists_cafes_ids  # , check_exists_dish
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


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
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.MANAGER, UserRole.ADMIN],
        ),
    ),
) -> DishInfo:
    """Создание нового блюда."""
    logger.info(
        'Пользователь %s инициировал создание Блюда %d',
        current_user.id,
        dish_in.name,
        extra={'user_id': str(current_user.id)},
    )

    # Проверка существования кафе
    await check_exists_cafes_ids(dish_in.cafes_id, session)

    # Логика создания блюда
    try:
        crud = crud_dish(session)
        new_dish = await crud.create_dish(dish_in)
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
