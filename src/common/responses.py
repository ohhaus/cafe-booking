"""Фабрика ответов API.

Содержит предопределенные ответы для различных HTTP статус кодов,
используемые в эндпоинтах API для обеспечения консистентности.
"""

from http import HTTPStatus
from typing import Any, Dict, Type

from pydantic import BaseModel

from src.common.schemas import CustomErrorResponse


def error_response(
    status_code: HTTPStatus,
    description: str,
    model: Type[BaseModel] = CustomErrorResponse,
) -> Dict[int, Dict[str, Any]]:
    """Создает шаблон ответа об ошибке с заданным статусом и описанием."""
    return {
        status_code.value: {
            'description': description,
            'content': {
                'application/json': {
                    'schema': model.model_json_schema(),
                },
            },
        },
    }


def success_response(
    status: HTTPStatus,
    model: Type[BaseModel],
    description: str = 'Успешно',
) -> Dict[int, Dict[str, Any]]:
    """Создает шаблон ответа о успешном создании объекта."""
    return {
        status.value: {
            'description': description,
            'content': {
                'application/json': {
                    'schema': model.model_json_schema(),
                },
            },
        },
    }


OK_RESPONSES = {
    HTTPStatus.OK.value: {'description': 'Успешно'},
}
