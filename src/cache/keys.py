import hashlib
from typing import Any
from uuid import UUID


def key_cafes_list(
    show_all: bool | None = None, user_role: str = 'user',
) -> str:
    """Ключ для списка кафе."""
    parts = ['cafes', f'role={user_role}']
    if show_all is not None:
        parts.append(f'show_all={show_all}')
    return ':'.join(parts)


def key_cafe(cafe_id: UUID, include_inactive: bool = False) -> str:
    """Ключ для кафе."""
    return f'cafe:{cafe_id}:inactive={include_inactive}'


def key_dishes_list(
    cafe_id: UUID | None = None, show_all: bool = False,
) -> str:
    """Ключ для списка блюд."""
    parts = ['dishes', f'show_all={show_all}']
    if cafe_id:
        parts.append(f'cafe={cafe_id}')
    return ':'.join(parts)


def key_dish(dish_id: UUID) -> str:
    """Ключ для блюда."""
    return f'dish:{dish_id}'


def key_cafe_tables(cafe_id: UUID) -> str:
    """Ключ для столов кафе."""
    return f'cafe:{cafe_id}:tables'


def key_cafe_table(cafe_id: UUID, table_id: UUID) -> str:
    """Ключ для стола."""
    return f'cafe:{cafe_id}:table:{table_id}'


def key_media(media_id: UUID) -> str:
    """Ключ для медиа."""
    return f'media:{media_id}'


def key_actions_list(active_only: bool = True) -> str:
    """Ключ для списка акций."""
    return f'actions:active={active_only}'


def key_action(action_id: UUID) -> str:
    """Ключ для акции."""
    return f'action:{action_id}'


def key_http_endpoint(
    method: str, path: str, query_params: dict[str, Any] | None = None,
) -> str:
    """Ключ для HTTP эндпоинта."""
    parts = ['http', method.upper(), path]

    if query_params:
        sorted_params = sorted(query_params.items())
        params_str = '&'.join(f'{k}={v}' for k, v in sorted_params)
        if len(params_str) > 50:
            params_str = hashlib.md5(params_str.encode()).hexdigest()[:8]
        parts.append(params_str)

    return ':'.join(parts)


def key_function_result(func_name: str, *args: Any, **kwargs: Any) -> str:
    """Ключ для результата функции."""
    args_hash = hashlib.md5(
        str(args).encode() + str(kwargs).encode(),
    ).hexdigest()[:8]
    return f'func:{func_name}:{args_hash}'
