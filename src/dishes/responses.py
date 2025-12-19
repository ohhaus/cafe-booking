"""Стандартные ответы API.

Содержит предопределенные ответы для различных HTTP статус кодов,
используемые в эндпоинтах API для обеспечения консистентности.

todo: вынести в общий модуль, если понадобится в других приложениях.
"""

from http import HTTPStatus
from typing import Any, Dict

from src.dishes.schemas import CustomErrorResponse, DishInfo


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

CREATED_RESPONSE = {
    HTTPStatus.CREATED.value: {
        "description": "Успешно",
        "content": {
            "application/json": {
                "schema": DishInfo.schema(),
            },
        },
    },
}

ERROR_400_RESPONSE = create_error_response(
    HTTPStatus.BAD_REQUEST,
    "Ошибка в параметрах запроса",
)

ERROR_401_RESPONSE = create_error_response(
    HTTPStatus.UNAUTHORIZED,
    "Неавторизированный пользователь",
)

ERROR_403_RESPONSE = create_error_response(
    HTTPStatus.FORBIDDEN,
    "Доступ запрещен",
)

ERROR_422_RESPONSE = create_error_response(
    HTTPStatus.UNPROCESSABLE_ENTITY,
    "Ошибка валидации данных",
)

# --- Ответы для Блюд ---
DISH_GET_RESPONSES = {**OK_RESPONSES,
                      **ERROR_401_RESPONSE,
                      **ERROR_422_RESPONSE}

DISH_CREATE_RESPONSES = {**CREATED_RESPONSE,
                         **ERROR_400_RESPONSE,
                         **ERROR_401_RESPONSE,
                         **ERROR_403_RESPONSE,
                         **ERROR_422_RESPONSE}
