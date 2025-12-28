import logging
from uuid import UUID

from .client import cache
from .keys import key_cafes_list, key_dishes_list


logger = logging.getLogger('app.cache')


async def invalidate_cafe(cafe_id: UUID) -> int:
    """Инвалидирует всё связанное с кафе."""
    patterns = [
        f'cafe:{cafe_id}:*',
        key_cafes_list(None) + '*',
        key_dishes_list(cafe_id) + '*',
    ]

    deleted = 0
    for pattern in patterns:
        deleted += await cache.delete_pattern(pattern)

    logger.info(f'Инвалидирован кэш кафе {cafe_id}')
    return deleted


async def invalidate_dish(dish_id: UUID) -> int:
    """Инвалидирует кэш блюда."""
    patterns = [
        f'dish:{dish_id}',
        key_dishes_list(None) + '*',
    ]

    deleted = 0
    for pattern in patterns:
        deleted += await cache.delete_pattern(pattern)

    logger.info(f'Инвалидирован кэш блюда {dish_id}')
    return deleted


async def invalidate_actions() -> int:
    """Инвалидирует кэш акций."""
    pattern = 'actions:*'
    deleted = await cache.delete_pattern(pattern)

    logger.info('Инвалидирован кэш акций')
    return deleted


async def invalidate_cafe_tables(cafe_id: UUID) -> int:
    """Инвалидирует кэш столов кафе."""
    pattern = f'cafe:{cafe_id}:tables*'
    deleted = await cache.delete_pattern(pattern)

    logger.info(f'Инвалидирован кэш столов кафе {cafe_id}')
    return deleted


async def invalidate_media(media_id: UUID) -> int:
    """Инвалидирует кэш медиа."""
    pattern = f'media:{media_id}'
    deleted = await cache.delete(pattern)

    logger.info(f'Инвалидирован кэш медиа {media_id}')
    return deleted


async def invalidate_all() -> int:
    """Инвалидирует весь кэш (только для админов)."""
    patterns = [
        'cafe:*',
        'cafes:*',
        'dish:*',
        'dishes:*',
        'action:*',
        'actions:*',
        'media:*',
        'http:*',
        'func:*',
    ]

    deleted = 0
    for pattern in patterns:
        deleted += await cache.delete_pattern(pattern)

    logger.warning(f'Полная инвалидация кэша: {deleted} ключей')
    return deleted
