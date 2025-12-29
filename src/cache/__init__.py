"""Redis cache module.

Основные компоненты:
    - RedisCache: асинхронный клиент с connection pooling
    - Декораторы: @cached, @auto_invalidate, @conditional_cache
    - Функции инвалидации: invalidate_cafe, invalidate_dish, etc.
    - Генераторы ключей: key_cafe, key_cafes_list, etc.

"""

from src.cache.client import RedisCache, cache, get_cache
from src.cache.decorators import (
    auto_invalidate,
    cached,
    conditional_cache,
)
from src.cache.invalidation import (
    invalidate_all_actions,
    invalidate_all_cafes,
    invalidate_all_dishes,
    invalidate_cafe,
    invalidate_cafe_tables,
    invalidate_dish,
    invalidate_media,
)
from src.cache.keys import (
    PREFIX_ACTION,
    PREFIX_ACTIONS,
    PREFIX_CAFE,
    PREFIX_CAFES,
    PREFIX_DISH,
    PREFIX_DISHES,
    PREFIX_FUNC,
    PREFIX_MEDIA,
    key_action,
    key_actions_list,
    key_cafe,
    key_cafe_pattern,
    key_cafe_table,
    key_cafe_tables,
    key_cafe_tables_pattern,
    key_cafes_list,
    key_dish,
    key_dishes_list,
    key_function_result,
    key_media,
    pattern_all_actions,
    pattern_all_cafes,
    pattern_all_dishes,
)


__all__ = [
    # Client
    'RedisCache',
    'cache',
    'get_cache',
    # Decorators
    'cached',
    'auto_invalidate',
    'conditional_cache',
    # Invalidation
    'invalidate_cafe',
    'invalidate_dish',
    'invalidate_all_cafes',
    'invalidate_all_dishes',
    'invalidate_all_actions',
    'invalidate_cafe_tables',
    'invalidate_media',
    # Keys - Prefixes
    'PREFIX_CAFE',
    'PREFIX_CAFES',
    'PREFIX_DISH',
    'PREFIX_DISHES',
    'PREFIX_ACTION',
    'PREFIX_ACTIONS',
    'PREFIX_MEDIA',
    'PREFIX_FUNC',
    # Keys - Functions
    'key_cafes_list',
    'key_cafe',
    'key_cafe_pattern',
    'key_dishes_list',
    'key_dish',
    'key_cafe_tables',
    'key_cafe_table',
    'key_cafe_tables_pattern',
    'key_actions_list',
    'key_action',
    'key_media',
    'key_function_result',
    # Keys - Patterns
    'pattern_all_cafes',
    'pattern_all_dishes',
    'pattern_all_actions',
]
