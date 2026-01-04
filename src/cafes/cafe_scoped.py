from __future__ import annotations

from typing import Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from src.cache.client import RedisCache
from src.cache.keys import key_cafe_meta
from src.cafes.models import Cafe
from src.common.exceptions import NotFoundException
from src.config import settings
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
    """Возвращает Cafe по id или None."""
    result = await db.execute(
        select(Cafe).where(Cafe.id == cafe_id),
    )
    return result.scalars().one_or_none()


async def get_cafe_meta_cached(
    db: AsyncSession,
    cafe_id: UUID,
    cache: RedisCache,
) -> dict:
    """Возвращает.

    {"exists": bool, "active": bool?},
    active присутствует только если exists=True.
    """

    async def loader() -> dict:
        result = await db.execute(
            select(Cafe.active).where(Cafe.id == cafe_id),
        )
        row = result.first()
        if row is None:
            return {'exists': False}
        return {'exists': True, 'active': bool(row[0])}

    return await cache.get_or_set(
        key=key_cafe_meta(cafe_id),
        ttl=settings.cache.TTL_CAFE_META,
        loader=loader,
    )


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
    show_all: bool = False,
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


async def ensure_cafe_exists_cached(
    db: AsyncSession,
    cafe_id: UUID,
    cache: RedisCache,
) -> dict:
    """Проверка на наличие кафе."""
    meta = await get_cafe_meta_cached(db, cafe_id, cache)
    if not meta['exists']:
        raise NotFoundException('Кафе не найдено.')
    return meta
