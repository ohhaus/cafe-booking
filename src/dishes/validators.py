# src/dishes/validators.py
from typing import Iterable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.common.exceptions import NotFoundException
from src.dishes.crud import dishes_crud
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
            detail=f'Блюдо с ID {dish_id} не найдено',
        )

    return dish


async def validate_active_cafes_ids(
    *,
    session: AsyncSession,
    cafes_ids: Iterable[UUID],
) -> Sequence[Cafe]:
    """Валидируем список переданных ИД Кафе, возвращаем только активный."""
    cafes_ids = list(dict.fromkeys(cafes_ids))

    cafes = await dishes_crud.get_active_cafes_by_ids(
        session=session,
        cafes_ids=cafes_ids,
    )
    requested = set(cafes_ids)
    found = {c.id for c in cafes}
    missing = requested - found
    if missing:
        raise NotFoundException(
            f'Не найдены или неактивны кафе с ID: {missing}'
        )

    return cafes
