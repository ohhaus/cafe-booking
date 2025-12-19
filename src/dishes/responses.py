"""Константы для стандартных ответов API.

Содержит предопределенные ответы для различных HTTP статус кодов,
используемые в эндпоинтах API для обеспечения консистентности.

todo: вынести в общий модуль, если понадобится в других приложениях.
"""

from typing import Any, Dict

from src.dishes.schemas import CustomErrorResponse


# --- Общие ответы ---
OK_RESPONSES: Dict[int, Dict[str, Any]] = {
    200: {"description": "Успешно"},
}

ERROR_RESPONSES: Dict[int, Dict[str, Any]] = {
    401: {
        "description": "Неавторизированный пользователь",
        "content": {
            "application/json": {
                "schema": CustomErrorResponse.schema(),
            },
        },
    },
    422: {
        "description": "Ошибка валидации данных",
        "content": {
            "application/json": {
                "schema": CustomErrorResponse.schema(),
            },
        },
    },
}

DISH_GET_RESPONSES = {**OK_RESPONSES, **ERROR_RESPONSES}
