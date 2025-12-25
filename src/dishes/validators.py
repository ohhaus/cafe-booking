from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.dishes.models import Dish


async def check_exists_dish(
    dish_id: int,
    session: AsyncSession,
) -> Dish:
    """Проверка существования блюда по ID."""
    result = await session.execute(
        select(Dish).where(Dish.id == dish_id, Dish.is_active),
    )
    dish = result.scalars().first()
    if not dish:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Блюдо не найдено',
        )
    return dish


async def check_exists_cafes_ids(
    cafes_id: list[int],
    session: AsyncSession,
) -> None:
    """Проверяет, что все кафе из списка существуют."""
    if not cafes_id:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Список ID кафе не может быть пустым.',
        )

    result = await session.execute(
        select(Cafe.id).where(
            Cafe.id.in_(cafes_id),
            Cafe.active.is_(True),
        ),
    )
    existing_ids = {row[0] for row in result.all()}

    missing = set(cafes_id) - existing_ids
    if missing:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Не все кафе существуют.',
        )
