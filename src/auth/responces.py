"""Стандартные ответы API.

Содержит предопределенные ответы для различных HTTP статус кодов,
используемые в эндпоинтах API для обеспечения консистентности.

todo: вынести в общий модуль, если понадобится в других приложениях.
"""

from http import HTTPStatus
from typing import Any, Dict

from src.common.schemas import CustomErrorResponse


def create_error_response(
        status_code: HTTPStatus, description: str,
        ) -> Dict[int, Dict[str, Any]]:
    """Создает шаблон ответа об ошибке с заданным статусом и описанием."""
    return {
        status_code.value: {
            "description": description,
            "content": {
                "application/json": {
                    "schema": CustomErrorResponse.schema(),
                },
            },
        },
    }


OK_RESPONSES = {
    HTTPStatus.OK.value: {"description": "Успешно"},
}

ERROR_422_RESPONSE = create_error_response(
    HTTPStatus.UNPROCESSABLE_ENTITY,
    "Ошибка валидации данных",
)

# --- Ответы для Блюд ---
LOGIN_RESPONSES = {**OK_RESPONSES,
                   **ERROR_422_RESPONSE}
