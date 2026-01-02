from typing import Any
from uuid import UUID


PREFIX_CAFE = 'cafe'
PREFIX_CAFES = 'cafes'
PREFIX_DISH = 'dish'
PREFIX_DISHES = 'dishes'
PREFIX_ACTION = 'action'
PREFIX_ACTIONS = 'actions'
PREFIX_MEDIA = 'media'


def _build_key(*parts: Any) -> str:
    """Формирует ключ Redis из частей, соединяя их через ':'.

    None-значения игнорируются.

    Example:
        >>> _build_key('media', UUID('...'))
        'media:<uuid>'

    """
    return ':'.join(str(p) for p in parts if p is not None)


def key_cafes_list(show_all: bool | None = None) -> str:
    """Возвращает ключ кэша для списка кафе."""
    parts = [PREFIX_CAFES, 'list']
    if show_all is not None:
        parts.append(f'show_all={str(show_all).lower()}')
    return _build_key(*parts)


def key_cafe(cafe_id: UUID) -> str:
    """Возвращает ключ кэша для кафе по идентификатору."""
    return _build_key(PREFIX_CAFE, cafe_id)


def key_cafe_active(cafe_id: UUID) -> str:
    """Возвращает ключ кэша для статуса активности кафе."""
    return _build_key(PREFIX_CAFE, cafe_id, 'active')


def pattern_cafe(cafe_id: UUID) -> str:
    """Возвращает шаблон ключей для одного кафе."""
    return f'{PREFIX_CAFE}:{cafe_id}*'


def pattern_all_cafes() -> str:
    """Возвращает шаблон ключей для всех кафе."""
    return f'{PREFIX_CAFES}*'


def key_cafe_tables(cafe_id: UUID) -> str:
    """Возвращает ключ кэша для списка столов кафе."""
    return _build_key(PREFIX_CAFE, cafe_id, 'tables')


def key_cafe_table(cafe_id: UUID, table_id: UUID) -> str:
    """Возвращает ключ кэша для конкретного стола кафе."""
    return _build_key(PREFIX_CAFE, cafe_id, 'table', table_id)


def key_cafe_table_active(cafe_id: UUID, table_id: UUID) -> str:
    """Возвращает ключ кэша для статуса активности стола в кафе."""
    return _build_key(PREFIX_CAFE, cafe_id, 'table', table_id, 'active')


def key_cafe_slot_active(cafe_id: UUID, slot_id: UUID) -> str:
    """Возвращает ключ кэша для статуса активности слота в кафе."""
    return _build_key(PREFIX_CAFE, cafe_id, 'slot', slot_id, 'active')


def pattern_cafe_tables(cafe_id: UUID) -> str:
    """Возвращает шаблон ключей для всех столов кафе."""
    return f'{PREFIX_CAFE}:{cafe_id}:table*'


def key_dishes_list(cafe_id: int | None = None, show_all: bool = False) -> str:
    """Возвращает ключ кэша для списка блюд."""
    parts = [PREFIX_DISHES, 'list']
    if cafe_id is not None:
        parts.append(f'cafe_id={cafe_id}')
    if show_all:
        parts.append('show_all=true')
    return _build_key(*parts)


def key_dish(dish_id: UUID) -> str:
    """Возвращает ключ кэша для блюда по идентификатору."""
    return _build_key(PREFIX_DISH, dish_id)


def pattern_all_dishes() -> str:
    """Возвращает шаблон ключей для всех блюд."""
    return f'{PREFIX_DISHES}*'


def key_actions_list() -> str:
    """Возвращает ключ кэша для списка акций."""
    return f'{PREFIX_ACTIONS}:list'


def key_action(action_id: UUID) -> str:
    """Возвращает ключ кэша для акции по идентификатору."""
    return _build_key(PREFIX_ACTION, action_id)


def pattern_all_actions() -> str:
    """Возвращает шаблон ключей для всех акций."""
    return f'{PREFIX_ACTIONS}*'


def key_media(media_id: UUID) -> str:
    """Возвращает ключ кэша для медиа-объекта."""
    return _build_key(PREFIX_MEDIA, media_id)
