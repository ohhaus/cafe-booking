from __future__ import annotations

from typing import Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from src.cafes.models import Cafe
from src.users.models import User


TModel = TypeVar('TModel')


def require_staff(
    user: User,
    message: str,
) -> None:
    """Хелпер, проверяет пользователя на то что он сотрудник."""
    if not user.is_staff():
        raise PermissionError(message)


async def get_cafe_or_none(
    db: AsyncSession,
    cafe_id: UUID,
) -> Optional[Cafe]:
    """Возвращает кафе по ID."""
    result = await db.execute(select(Cafe).where(Cafe.id == cafe_id))
    return result.scalars().first()


def cafe_scoped_stmt(model: Type[TModel], cafe_id: UUID) -> Select:
    """Возвращает запрос слота к определенному кафе."""
    return (
        select(model)
        .options(selectinload(model.cafe))
        .where(model.cafe_id == cafe_id)
    )


def with_id(model: Type[TModel], stmt: Select, obj_id: UUID) -> Select:
    """Возвращает запрос определенного слота по ID."""
    return stmt.where(model.id == obj_id)


def apply_visibility_filters(
    model: Type[TModel],
    stmt: Select,
    current_user: User,
    *,
    show_all: Optional[bool] = False,
) -> Select:
    """Правила видимости объектов.

    - staff:
        show_all=False -> только активные.
        show_all=True -> все.
    - user:
        только активные,
        и только если Cafe.active=True.
    """
    if current_user.is_staff():
        if show_all is False:
            return stmt.where(model.active.is_(True))
        return stmt

    return (
        stmt.where(model.active.is_(True))
        .join(Cafe, Cafe.id == model.cafe_id)
        .where(Cafe.active.is_(True))
    )
