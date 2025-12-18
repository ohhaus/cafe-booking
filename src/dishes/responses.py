"""Константы для стандартных ответов API.

Содержит предопределенные ответы для различных HTTP статус кодов,
используемые в эндпоинтах API для обеспечения консистентности.

todo: вынести в общий модуль, если понадобится в других приложениях.
"""

from typing import Any, Dict


# --- Общие ответы ---
COMMON_RESPONSES: Dict[int, Dict[str, Any]] = {
    404: {"description": "Ресурс не найден"},
    500: {"description": "Внутренняя ошибка сервера"},
}

DISH_RESPONSES: Dict[int, Dict[str, Any]] = {
    200: {"description": "Блюдо успешно получено"},
    201: {"description": "Блюдо создано"},
    400: {"description": "Ошибка в данных"},
    **COMMON_RESPONSES,
}

DISH_CREATE_RESPONSES = {201: {"description": "Блюдо создано"},
                         **DISH_RESPONSES}
DISH_GET_RESPONSES = {**DISH_RESPONSES}
DISH_UPDATE_RESPONSES = {200: {"description": "Блюдо обновлено"},
                         **DISH_RESPONSES}
DISH_DELETE_RESPONSES = {200: {"description": "Блюдо удалено"},
                         **DISH_RESPONSES}
