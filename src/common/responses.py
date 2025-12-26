"""Стандартные ответы API.

Содержит предопределенные ответы для различных HTTP статус кодов,
используемые в эндпоинтах API для обеспечения консистентности.
"""

from http import HTTPStatus
from typing import Any, Dict

from src.common.schemas import CustomErrorResponse
from src.dishes.schemas import DishInfo


def create_error_response(
    status_code: HTTPStatus,
    description: str,
) -> Dict[int | str, Dict[str, Any]]:
    """Создает шаблон ответа об ошибке с заданным статусом и описанием."""
    return {
        status_code.value: {
            'description': description,
            'content': {
                'application/json': {
                    'schema': CustomErrorResponse.schema(),
                },
            },
        },
    }


OK_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    HTTPStatus.OK.value: {'description': 'Успешно'},
}

CREATED_RESPONSE: Dict[int | str, Dict[str, Any]] = {
    HTTPStatus.CREATED.value: {
        'description': 'Успешно',
        'content': {
            'application/json': {
                'schema': DishInfo.schema(),
            },
        },
    },
}

# --- Базовые ошибки ---
ERROR_400_RESPONSE = create_error_response(
    HTTPStatus.BAD_REQUEST,
    'Ошибка в параметрах запроса',
)

ERROR_401_RESPONSE = create_error_response(
    HTTPStatus.UNAUTHORIZED,
    'Неавторизированный пользователь',
)

ERROR_403_RESPONSE = create_error_response(
    HTTPStatus.FORBIDDEN,
    'Доступ запрещен',
)

ERROR_404_RESPONSE = create_error_response(
    HTTPStatus.NOT_FOUND,
    'Данные не найдены',
)

ERROR_422_RESPONSE = create_error_response(
    HTTPStatus.UNPROCESSABLE_ENTITY,
    'Ошибка валидации данных',
)

DISH_GET_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    **OK_RESPONSES,
    **ERROR_401_RESPONSE,
    **ERROR_422_RESPONSE,
}

DISH_CREATE_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    **CREATED_RESPONSE,
    **ERROR_400_RESPONSE,
    **ERROR_401_RESPONSE,
    **ERROR_403_RESPONSE,
    **ERROR_422_RESPONSE,
}

DISH_GET_BY_ID_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    **OK_RESPONSES,
    **ERROR_400_RESPONSE,
    **ERROR_401_RESPONSE,
    **ERROR_403_RESPONSE,
    **ERROR_404_RESPONSE,
    **ERROR_422_RESPONSE,
}

LOGIN_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    **OK_RESPONSES,
    **ERROR_422_RESPONSE,
    **ERROR_403_RESPONSE,
}
