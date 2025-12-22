"""Стандартные ответы API."""

from http import HTTPStatus
from typing import Any, Dict

from src.common.schemas import CustomErrorResponse


def create_error_response(
    status_code: HTTPStatus,
    description: str,
) -> Dict[int, Dict[str, Any]]:
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


OK_RESPONSES = {
    HTTPStatus.OK.value: {'description': 'Успешно'},
}

ERROR_422_RESPONSE = create_error_response(
    HTTPStatus.UNPROCESSABLE_ENTITY,
    'Ошибка валидации данных',
)

ERROR_403_RESPONSE = create_error_response(
    HTTPStatus.FORBIDDEN,
    'Доступ запрещен',
)

LOGIN_RESPONSES = {
    **OK_RESPONSES,
    **ERROR_422_RESPONSE,
    **ERROR_403_RESPONSE,
}
