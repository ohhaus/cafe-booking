# src.common.responses.py
"""Фабрика ответов API.

Формирует пресеты ответов API.
"""

from http import HTTPStatus
from typing import Any, Dict, Iterable, Optional, Type

from pydantic import BaseModel

from src.common.schemas import CustomErrorResponse


def error_response(
    status_code: HTTPStatus,
    description: str,
    model: Type[BaseModel] = CustomErrorResponse,
) -> Dict[int, Dict[str, Any]]:
    """Сформировать шаблон ответа для ошибки в формате FastAPI `responses`.

    Используется для унификации описаний ошибок в OpenAPI и повторного
    применения в разных эндпоинтах.
    """
    return {
        status_code.value: {
            'description': description,
            'model': model,
        },
    }


def success_response(
    status: HTTPStatus,
    model: Type[BaseModel],
    description: str = 'Успешно',
) -> Dict[int, Dict[str, Any]]:
    """Сформировать шаблон успешного ответа в формате FastAPI `responses`.

    Обычно используется для документирования ответов, содержащих тело JSON
    с объектом (например, 201 Created с созданной сущностью).
    """
    return {
        status.value: {
            'description': description,
            'model': model,
        },
    }


OK_RESPONSES = {
    HTTPStatus.OK.value: {'description': 'Успешно'},
}

ERROR_400 = error_response(
    HTTPStatus.BAD_REQUEST,
    'Ошибка в параметрах запроса',
)
ERROR_401 = error_response(
    HTTPStatus.UNAUTHORIZED,
    'Неавторизированный пользователь',
)
ERROR_403 = error_response(
    HTTPStatus.FORBIDDEN,
    'Доступ запрещен',
)
ERROR_404 = error_response(
    HTTPStatus.NOT_FOUND,
    'Данные не найдены',
)
ERROR_409 = error_response(
    HTTPStatus.CONFLICT,
    'Конфликт данных',
)
ERROR_422 = error_response(
    HTTPStatus.UNPROCESSABLE_ENTITY,
    'Ошибка валидации данных',
)


Responses = Dict[int, Dict[str, Any]]

_ERROR_BY_STATUS: dict[HTTPStatus, Responses] = {
    HTTPStatus.BAD_REQUEST: ERROR_400,
    HTTPStatus.UNAUTHORIZED: ERROR_401,
    HTTPStatus.FORBIDDEN: ERROR_403,
    HTTPStatus.NOT_FOUND: ERROR_404,
    HTTPStatus.CONFLICT: ERROR_409,
    HTTPStatus.UNPROCESSABLE_ENTITY: ERROR_422,
}


def make_responses(
    *,
    ok: bool = True,
    created_model: Optional[Type[BaseModel]] = None,
    errors: Iterable[HTTPStatus] = (),
) -> Responses:
    """Собрать итоговый словарь `responses` из предопределённых частей.

    Позволяет декларативно собрать набор ответов:
    - опционально добавить 200 OK (только description);
    - опционально добавить 201 Created с указанной Pydantic-моделью;
    - добавить набор стандартных ошибок из `errors`.
    """
    resp = {}

    if ok:
        resp.update(OK_RESPONSES)

    if created_model is not None:
        resp.update(success_response(HTTPStatus.CREATED, created_model))

    for status in errors:
        try:
            resp.update(_ERROR_BY_STATUS[status])
        except KeyError as e:
            raise ValueError(
                f'Unsupported error status: {status}',
            ) from e
    return resp


def list_responses() -> Responses:
    """Получить пресет `responses` для эндпоинтов получения списка.

    (обычно GET /resource)
    Включает типовые ошибки авторизации и валидации входных параметров.

    Returns:
        Набор `responses`, подходящий для list-endpoint'ов.

    """
    return make_responses(
        errors=(
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )


def create_responses(model: Type[BaseModel]) -> Responses:
    """Получить пресет `responses` для эндпоинтов создания ресурса.

    (обычно POST /resource)
    Включает:
    - 201 Created со схемой `model`;
    - типовые ошибки: 400/401/403/422.
    200 OK намеренно не добавляется (`ok=False`),
    чтобы документация не выглядела двусмысленно.
    """
    return make_responses(
        ok=False,
        created_model=model,
        errors=(
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.CONFLICT,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )


def update_responses(model: Type[BaseModel]) -> Responses:
    """Получить пресет `responses` для эндпоинтов частичного обновления.

    (обычно PATCH /resource/{id})
    Включает:
    - 200 OK со схемой `model`;
    - типовые ошибки: 400/401/403/404/422.
    """
    return make_responses(
        errors=(
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
            HTTPStatus.CONFLICT,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )


def retrieve_responses() -> Responses:
    """Получить пресет `responses` для получения/обновления одного ресурса.

    (GET/PATCH /resource/{id})
    Включает типовые ошибки:
    - 400 (плохие параметры),
    - 401/403 (доступ),
    - 404 (ресурс не найден),
    - 422 (валидация).
    """
    return make_responses(
        errors=(
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )


def login_responses() -> Responses:
    """Получить пресет `responses` для эндпоинтов аутентификации.

    Включает ошибки, которые могут возникать при попытке логина:
    - 422 (ошибка валидации данных).
    """
    return make_responses(
        errors=(HTTPStatus.UNPROCESSABLE_ENTITY,),
    )


def user_list_responses() -> Responses:
    """Пресет `responses` для эндпоинта получения списка пользователей.

    Включает:
    - 200 OK,
    - 401 Unauthorized (неавторизован),
    - 403 Forbidden (нет прав на просмотр списка пользователей).
    """
    return make_responses(
        errors=(
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ),
    )


def user_create_response(model: Type[BaseModel]) -> Responses:
    """Пресет `responses` для регистрации нового пользователя.

    Включает:
    - 201 Created с указанной моделью ответа,
    - 400 Bad Request (ошибка в параметрах запроса/бизнес-правилах),
    - 422 Unprocessable Entity (валидация тела запроса).
    """
    return make_responses(
        ok=False,
        created_model=model,
        errors=(
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )


def user_retrieve_responses() -> Responses:
    """Пресет `responses` для получения пользователя по ID.

    Включает:
    - 200 OK,
    - 401 Unauthorized,
    - 403 Forbidden,
    - 404 Not Found,
    - 422 Unprocessable Entity (валидация path-параметра).
    """
    return make_responses(
        errors=(
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )


def user_me_patch_responses() -> Responses:
    """Пресет `responses` для обновления текущего пользователя.

    Включает:
    - 200 OK,
    - 400 Bad Request,
    - 401 Unauthorized,
    - 422 Unprocessable Entity.
    """
    return make_responses(
        errors=(
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    )
