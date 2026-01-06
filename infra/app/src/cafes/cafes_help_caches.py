import logging
from typing import Any, Sequence, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from src.cache.client import RedisCache
from src.cache.keys import (
    key_cafe_meta,
    pattern_all_cafes,
    pattern_cafe,
    pattern_cafe_slot,
    pattern_cafe_slots_list,
    pattern_cafe_table,
    pattern_manager_cud_cafe,
)


logger = logging.getLogger('app')

T = TypeVar('T', bound=BaseModel)


async def cache_get_list(
    cache: RedisCache,
    key: str,
    schema: Type[T],
) -> list[dict] | None:
    """Пробует достать список из кэша. Если формат битый — удаляет ключ."""
    cached = await cache.get(key)
    if cached is None:
        return None
    if not isinstance(cached, list):
        logger.warning('CACHE BAD %s (expected list, drop key)', key)
        await cache.delete(key)
        return None

    try:
        for item in cached:
            if not isinstance(item, dict):
                logger.warning(
                    'CACHE BAD %s (list item not dict, drop key)',
                    key,
                )
                await cache.delete(key)
                return None
            schema.model_validate(item)
        return cached
    except ValidationError:
        logger.warning(
            'CACHE BAD %s (schema validation failed, drop key)',
            key,
        )
        await cache.delete(key)
        return None


async def cache_get_one(
    cache: RedisCache,
    key: str,
    schema: Type[T],
) -> dict | None:
    """Пробует достать объект из кэша. Если формат битый — удаляет ключ."""
    cached = await cache.get(key)
    if cached is None:
        return None
    if not isinstance(cached, dict):
        logger.warning('CACHE BAD %s (expected dict, drop key)', key)
        await cache.delete(key)
        return None
    try:
        schema.model_validate(cached)
        return cached
    except ValidationError:
        logger.warning(
            'CACHE BAD %s (schema validation failed, drop key)',
            key,
        )
        await cache.delete(key)
        return None


async def cache_set(
    cache: RedisCache,
    key: str,
    payload: object,
    ttl: int,
) -> None:
    """Единая точка записи в кэш (чтоб не размазывать set по ручкам)."""
    if ttl <= 0:
        logger.warning('CACHE SKIP %s (ttl=%s)', key, ttl)
        return
    await cache.set(key, payload, ttl=ttl)


def dump_one(
    schema: Type[T],
    obj: Any,
) -> dict:
    """Единая сериализация ORM/Pydantic -> dict."""
    return schema.model_validate(obj).model_dump(
        mode='json',
        by_alias=True,
    )


def dump_list(
    schema: Type[T],
    objs: Sequence[Any],
) -> list[dict]:
    """Сериализация списка объектов."""
    return [dump_one(schema, obj) for obj in objs]


async def invalidate_slots_cache(
    cache: RedisCache,
    cafe_id: UUID,
) -> None:
    """Сносит кэш слотов (и список, и детали) для кафе."""
    await cache.delete_pattern(pattern_cafe_slot(cafe_id))
    await cache.delete_pattern(pattern_cafe_slots_list(cafe_id))


async def invalidate_tables_cache(
    cache: RedisCache,
    cafe_id: UUID,
) -> None:
    """Сносит кэш столов (и список, и детали) для кафе."""
    await cache.delete_pattern(pattern_cafe_table(cafe_id))


async def invalidate_cafes_cache(cache: RedisCache, cafe_id: UUID) -> None:
    """Сносит кэш, связанный с кафе."""
    await cache.delete_pattern(pattern_all_cafes())
    await cache.delete_pattern(pattern_cafe(cafe_id))
    await cache.delete(key_cafe_meta(cafe_id))
    await cache.delete_pattern(pattern_manager_cud_cafe(cafe_id))

    await invalidate_slots_cache(cache, cafe_id)
    await invalidate_tables_cache(cache, cafe_id)
