"""Redis cache module.

Основные компоненты:
- RedisCache: асинхронный клиент с connection pooling
- Декораторы: @cached, @cache_endpoint, @auto_invalidate
- Функции инвалидации: invalidate_cafe, invalidate_dish, etc.
- Генераторы ключей: key_cafe, key_cafes_list, etc.
"""

from .client import RedisCache, cache, get_cache
from .decorators import (
    auto_invalidate,
    cache_endpoint,
    cached,
    conditional_cache,
)
from .invalidation import (
    invalidate_all_actions,
    invalidate_all_cafes,
    invalidate_all_dishes,
    invalidate_cafe,
    invalidate_cafe_tables,
    invalidate_dish,
    invalidate_media,
)
from .keys import (
    PREFIX_ACTION,
    PREFIX_ACTIONS,
    PREFIX_CAFE,
    PREFIX_CAFES,
    PREFIX_DISH,
    PREFIX_DISHES,
    PREFIX_FUNC,
    PREFIX_HTTP,
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
    key_http_endpoint,
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
    'cache_endpoint',
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
    'PREFIX_HTTP',
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
    'key_http_endpoint',
    'key_function_result',
    # Keys - Patterns
    'pattern_all_cafes',
    'pattern_all_dishes',
    'pattern_all_actions',
]
