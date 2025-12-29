# src/dishes/validators.py
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.common.exceptions import BadRequestException, NotFoundException
from src.dishes.models import Dish


async def check_exists_dish(
    dish_id: UUID,
    session: AsyncSession,
) -> Dish:
    """Проверка существования блюда по ID.

    Args:
        dish_id: UUID блюда
        session: Сессия БД

    Returns:
        Объект Dish

    Raises:
        NotFoundException: Если блюдо не найдено

    """
    result = await session.execute(
        select(Dish).where(Dish.id == dish_id),
    )
    dish = result.scalars().first()

    if not dish:
        raise NotFoundException(
            detail=f"Блюдо с ID {dish_id} не найдено",
        )

    return dish


async def check_exists_cafes_ids(
    cafes_ids: list[UUID],
    session: AsyncSession,
) -> list[Cafe]:
    """Проверяет, что все кафе из списка существуют и активны.

    Args:
        cafes_ids: Список UUID кафе
        session: Сессия БД

    Returns:
        Список объектов Cafe

    Raises:
        BadRequestException: Если список пуст
        NotFoundException: Если не все кафе существуют

    """
    # Проверка на пустой список
    if not cafes_ids:
        raise BadRequestException(
            message="Список ID кафе не может быть пустым",
        )

    # Получаем все существующие и активные кафе
    result = await session.execute(
        select(Cafe).where(
            Cafe.id.in_(cafes_ids),
            Cafe.active.is_(True),
        ),
    )
    existing_cafes = result.scalars().all()
    existing_ids = {cafe.id for cafe in existing_cafes}

    # Проверяем, что все запрошенные кафе найдены
    missing = set(cafes_ids) - existing_ids
    if missing:
        raise NotFoundException(
            message=f"Кафе с ID {missing} не найдены или неактивны",
        )

    return existing_cafes
