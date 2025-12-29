"""Модуль генерации ключей для Redis кэша.

Все ключи имеют entity-like формат для удобства и читаемости:
- Списки: 'cafes:list', 'dishes:list:show_all=true'
- Объекты: 'cafe:uuid', 'dish:uuid'
- Вложенные: 'cafe:uuid:tables', 'cafe:uuid:table:uuid'

Примеры:
    cafes:list
    cafes:list:show_all=true
    cafe:123e4567-e89b-12d3-a456-426614174000
    dishes:list:cafe_id=1
    dish:123e4567-e89b-12d3-a456-426614174000
"""

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
PREFIX_FUNC = 'func'


def _build_key(*parts: Any) -> str:
    """Универсальный построитель ключей.

    Args:
        *parts: Части ключа для объединения

    Returns:
        str: Ключ в формате 'part1:part2:part3'

    Example:
        >>> _build_key('cafe', uuid4(), 'tables')
        'cafe:123e4567-e89b-12d3-a456-426614174000:tables'

    """
    return ':'.join(str(part) for part in parts if part is not None)


def key_cafes_list(show_all: bool | None = None) -> str:
    """Ключ для списка кафе.

    Args:
        show_all: Флаг показа всех кафе (включая неактивные)

    Returns:
        str: Ключ кэша

    Example:
        >>> key_cafes_list()
        'cafes:list'
        >>> key_cafes_list(show_all=True)
        'cafes:list:show_all=true'

    """
    parts = [PREFIX_CAFES, 'list']
    if show_all is not None:
        parts.append(f'show_all={str(show_all).lower()}')
    return _build_key(*parts)


def key_cafe(cafe_id: UUID) -> str:
    """Ключ для кафе.

    Args:
        cafe_id: ID кафе

    Returns:
        str: Ключ кэша

    Example:
        >>> key_cafe(UUID('123e4567-e89b-12d3-a456-426614174000'))
        'cafe:123e4567-e89b-12d3-a456-426614174000'

    """
    return _build_key(PREFIX_CAFE, cafe_id)


def key_cafe_pattern(cafe_id: UUID) -> str:
    """Паттерн для всех ключей кафе.

    Args:
        cafe_id: ID кафе

    Returns:
        str: Паттерн для Redis SCAN

    Example:
        >>> key_cafe_pattern(UUID('123e4567-...'))
        'cafe:123e4567-...*'

    """
    return f'{PREFIX_CAFE}:{cafe_id}*'


def pattern_all_cafes() -> str:
    """Паттерн для всех кэшей кафе.

    Returns:
        str: Паттерн для Redis SCAN

    Example:
        >>> pattern_all_cafes()
        'cafes*'

    """
    return f'{PREFIX_CAFES}*'


def key_dishes_list(
    cafe_id: int | None = None,
    show_all: bool = False,
) -> str:
    """Ключ для списка блюд.

    Args:
        cafe_id: ID кафе для фильтрации (опционально)
        show_all: Флаг показа всех блюд

    Returns:
        str: Ключ кэша

    Example:
        >>> key_dishes_list()
        'dishes:list'
        >>> key_dishes_list(cafe_id=1, show_all=True)
        'dishes:list:cafe_id=1:show_all=true'

    """
    parts = [PREFIX_DISHES, 'list']
    if cafe_id is not None:
        parts.append(f'cafe_id={cafe_id}')
    if show_all:
        parts.append('show_all=true')
    return _build_key(*parts)


def key_dish(dish_id: UUID) -> str:
    """Ключ для блюда.

    Args:
        dish_id: ID блюда

    Returns:
        str: Ключ кэша

    Example:
        >>> key_dish(UUID('123e4567-e89b-12d3-a456-426614174000'))
        'dish:123e4567-e89b-12d3-a456-426614174000'

    """
    return _build_key(PREFIX_DISH, dish_id)


def pattern_all_dishes() -> str:
    """Паттерн для всех кэшей блюд.

    Returns:
        str: Паттерн для Redis SCAN

    Example:
        >>> pattern_all_dishes()
        'dishes*'

    """
    return f'{PREFIX_DISHES}*'


def key_cafe_tables(cafe_id: UUID) -> str:
    """Ключ для списка столов кафе.

    Args:
        cafe_id: ID кафе

    Returns:
        str: Ключ кэша

    Example:
        >>> key_cafe_tables(UUID('123e4567-...'))
        'cafe:123e4567-...:tables'

    """
    return _build_key(PREFIX_CAFE, cafe_id, 'tables')


def key_cafe_table(cafe_id: UUID, table_id: UUID) -> str:
    """Ключ для конкретного стола.

    Args:
        cafe_id: ID кафе
        table_id: ID стола

    Returns:
        str: Ключ кэша

    Example:
        >>> key_cafe_table(cafe_uuid, table_uuid)
        'cafe:123e4567-...:table:987fcdeb-...'

    """
    return _build_key(PREFIX_CAFE, cafe_id, 'table', table_id)


def key_cafe_tables_pattern(cafe_id: UUID) -> str:
    """Паттерн для всех столов кафе.

    Args:
        cafe_id: ID кафе

    Returns:
        str: Паттерн для Redis SCAN

    Example:
        >>> key_cafe_tables_pattern(UUID('123e4567-...'))
        'cafe:123e4567-...:table*'

    """
    return f'{PREFIX_CAFE}:{cafe_id}:table*'


def key_actions_list() -> str:
    """Ключ для списка акций.

    Returns:
        str: Ключ кэша

    Example:
        >>> key_actions_list()
        'actions:list'

    """
    return f'{PREFIX_ACTIONS}:list'


def key_action(action_id: UUID) -> str:
    """Ключ для акции.

    Args:
        action_id: ID акции

    Returns:
        str: Ключ кэша

    Example:
        >>> key_action(UUID('123e4567-...'))
        'action:123e4567-...'

    """
    return _build_key(PREFIX_ACTION, action_id)


def pattern_all_actions() -> str:
    """Паттерн для всех кэшей акций.

    Returns:
        str: Паттерн для Redis SCAN

    Example:
        >>> pattern_all_actions()
        'actions*'

    """
    return f'{PREFIX_ACTIONS}*'


def key_media(media_id: UUID) -> str:
    """Ключ для медиа.

    Args:
        media_id: ID медиа файла

    Returns:
        str: Ключ кэша

    Example:
        >>> key_media(UUID('123e4567-...'))
        'media:123e4567-...'

    """
    return _build_key(PREFIX_MEDIA, media_id)


def key_function_result(
    func_name: str,
    *args: Any,
    **kwargs: Any,
) -> str:
    """Ключ для результата функции.

    Args:
        func_name: Имя функции
        *args: Позиционные аргументы функции
        **kwargs: Именованные аргументы функции

    Returns:
        str: Ключ кэша с хэшем аргументов

    Example:
        >>> key_function_result('get_user', 123, active=True)
        'func:get_user:a1b2c3d4'

    """
    args_hash = hashlib.md5(
        str(args).encode() + str(kwargs).encode(),
    ).hexdigest()[:8]
    return _build_key(PREFIX_FUNC, func_name, args_hash)
