import hashlib
from typing import Any
from uuid import UUID


PREFIX_CAFE = 'cafe'
PREFIX_CAFES = 'cafes'
PREFIX_DISH = 'dish'
PREFIX_DISHES = 'dishes'
PREFIX_ACTION = 'action'
PREFIX_ACTIONS = 'actions'
PREFIX_MEDIA = 'media'
PREFIX_HTTP = 'http'
PREFIX_FUNC = 'func'


def _build_key(*parts: Any) -> str:
    """Универсальный построитель ключей."""
    return ':'.join(str(part) for part in parts if part is not None)


def key_cafes_list(show_all: bool | None = None) -> str:
    """Ключ для списка кафе."""
    parts = [PREFIX_CAFES]
    if show_all is not None:
        parts.append(f'show_all={show_all}')
    return _build_key(*parts)


def key_cafe(cafe_id: UUID) -> str:
    """Ключ для кафе."""
    return _build_key(PREFIX_CAFE, cafe_id)


def key_cafe_pattern(cafe_id: UUID) -> str:
    """Паттерн для всех ключей кафе."""
    return f'{PREFIX_CAFE}:{cafe_id}*'


def pattern_all_cafes() -> str:
    """Паттерн для всех кэшей кафе."""
    return f'{PREFIX_CAFES}*'


def key_dishes_list(cafe_id: int | None = None, show_all: bool = False) -> str:
    """Ключ для списка блюд."""
    parts = [PREFIX_DISHES, f'show_all={show_all}']
    if cafe_id is not None:
        parts.append(f'cafe={cafe_id}')
    return _build_key(*parts)


def key_dish(dish_id: UUID) -> str:
    """Ключ для блюда."""
    return _build_key(PREFIX_DISH, dish_id)


def pattern_all_dishes() -> str:
    """Паттерн для всех кэшей блюд."""
    return f'{PREFIX_DISHES}*'


def key_cafe_tables(cafe_id: UUID) -> str:
    """Ключ для списка столов кафе."""
    return _build_key(PREFIX_CAFE, cafe_id, 'tables')


def key_cafe_table(cafe_id: UUID, table_id: UUID) -> str:
    """Ключ для конкретного стола."""
    return _build_key(PREFIX_CAFE, cafe_id, 'table', table_id)


def key_cafe_tables_pattern(cafe_id: UUID) -> str:
    """Паттерн для всех столов кафе."""
    return f'{PREFIX_CAFE}:{cafe_id}:table*'


def key_actions_list() -> str:
    """Ключ для списка акций."""
    return f'{PREFIX_ACTIONS}:list'


def key_action(action_id: UUID) -> str:
    """Ключ для акции."""
    return _build_key(PREFIX_ACTION, action_id)


def pattern_all_actions() -> str:
    """Паттерн для всех кэшей акций."""
    return f'{PREFIX_ACTIONS}*'


def key_media(media_id: UUID) -> str:
    """Ключ для медиа."""
    return _build_key(PREFIX_MEDIA, media_id)


def key_http_endpoint(
    method: str,
    path: str,
    query_params: dict[str, Any] | None = None,
) -> str:
    """Ключ для HTTP эндпоинта."""
    parts = [PREFIX_HTTP, method.upper(), path]

    if query_params:
        sorted_params = sorted(query_params.items())
        params_str = '&'.join(f'{k}={v}' for k, v in sorted_params)
        if len(params_str) > 50:
            params_str = hashlib.md5(params_str.encode()).hexdigest()[:8]
        parts.append(params_str)

    return _build_key(*parts)


def key_function_result(func_name: str, *args: Any, **kwargs: Any) -> str:
    """Ключ для результата функции."""
    args_hash = hashlib.md5(
        str(args).encode() + str(kwargs).encode(),
    ).hexdigest()[:8]
    return _build_key(PREFIX_FUNC, func_name, args_hash)
