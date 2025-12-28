import logging
from typing import Sequence
from uuid import UUID

from .client import cache
from .keys import (
    key_cafe_pattern,
    key_cafe_tables_pattern,
    key_dish,
    key_media,
    pattern_all_actions,
    pattern_all_cafes,
    pattern_all_dishes,
)


logger = logging.getLogger('app.cache')


async def _invalidate_patterns(
    patterns: Sequence[str],
    entity_name: str = 'cache',
    entity_id: str | UUID | None = None,
) -> int:
    """Базовая функция для инвалидации кэша по паттернам (DRY).

    Args:
        patterns: Список паттернов для удаления
        entity_name: Имя сущности для логирования
        entity_id: ID сущности для логирования

    Returns:
        Количество удалённых ключей

    """
    deleted = 0
    for pattern in patterns:
        deleted += await cache.delete_pattern(pattern)

    log_msg = f'Инвалидирован кэш {entity_name}'
    if entity_id:
        log_msg += f' {entity_id}'
    log_msg += f': {deleted} ключей'

    logger.info(log_msg)
    return deleted


async def invalidate_cafe(cafe_id: UUID) -> int:
    """Инвалидирует всё связанное с кафе."""
    patterns = [
        key_cafe_pattern(cafe_id),  # cafe:{id}*
        pattern_all_cafes(),  # cafes*
    ]
    return await _invalidate_patterns(patterns, 'кафе', cafe_id)


async def invalidate_all_cafes() -> int:
    """Инвалидирует все кэши кафе."""
    patterns = [pattern_all_cafes()]
    return await _invalidate_patterns(patterns, 'всех кафе')


async def invalidate_dish(dish_id: UUID) -> int:
    """Инвалидирует кэш блюда."""
    deleted = await cache.delete(key_dish(dish_id))
    deleted += await cache.delete_pattern(pattern_all_dishes())
    logger.info(f'Инвалидирован кэш блюда {dish_id}: {deleted} ключей')
    return deleted


async def invalidate_all_dishes() -> int:
    """Инвалидирует все кэши блюд."""
    patterns = [pattern_all_dishes()]
    return await _invalidate_patterns(patterns, 'всех блюд')


async def invalidate_cafe_tables(cafe_id: UUID) -> int:
    """Инвалидирует кэш столов кафе."""
    patterns = [key_cafe_tables_pattern(cafe_id)]
    return await _invalidate_patterns(patterns, 'столов кафе', cafe_id)


async def invalidate_all_actions() -> int:
    """Инвалидирует кэш акций."""
    patterns = [pattern_all_actions()]
    return await _invalidate_patterns(patterns, 'всех акций')


async def invalidate_media(media_id: UUID) -> int:
    """Инвалидирует кэш медиа."""
    deleted = await cache.delete(key_media(media_id))
    logger.info(f'Инвалидирован кэш медиа {media_id}')
    return deleted
