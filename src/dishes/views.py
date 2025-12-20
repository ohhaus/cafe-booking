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
    DISH_GET_BY_ID_RESPONSES,
    DISH_GET_RESPONSES,
)
from src.dishes.schemas import DishCreate, DishInfo, DishUpdate
from src.dishes.validators import check_exists_cafes_ids, check_exists_dish
from src.users.dependencies import require_roles
from src.users.models import User


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
    current_user: User = Depends(require_roles(allow_guest=False)),
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
    dish_id: int,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> DishInfo:
    """Получение информации о блюде по его ID."""
    try:
        crud = crud_dish(session)
        is_staff = current_user.is_staff()

        # Получаем блюдо по ID
        dish = await crud.get_dish_by_id(dish_id=dish_id)

        # Проверка на наличие блюда
        if not dish:
            logger.info('Блюдо с ID %d не найдено', dish_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Данные не найдены",
                )

        # Если пользователь не является администратором или менеджером,
        # проверяем статус блюда
        if not is_staff and not dish.is_active:
            logger.info('Доступ к неактивному блюду для пользователя с ID %d',
                        current_user.id,
                        )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен",
                )

        return dish

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error('Ошибка при получении блюда: %s', str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка в параметрах запроса",
            )


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
    try:
        crud = crud_dish(session)
        is_staff = current_user.is_staff()

        # Проверяем, что пользователь имеет право на обновление
        if not is_staff:
            logger.info(
                'Пользователь с ID %d не имеет прав для обновления блюда',
                current_user.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен")

        # Проверяем, существует ли блюдо
        await check_exists_dish(dish_id, session)

        dish = await crud.get(dish_id)

        # Обновляем данные блюда
        update_dish = await crud.update_dish(
            dish,
            dish_update=dish_update)
        return DishInfo.model_validate(update_dish)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error('Ошибка при обновлении блюда: %s', str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка в параметрах запроса")
