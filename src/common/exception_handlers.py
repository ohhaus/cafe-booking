# src/common/exception_handlers.py
"""Обработчики исключений для FastAPI приложения."""

from http import HTTPStatus
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.common.exceptions import AppException
from src.common.schemas import CustomErrorResponse


logger = logging.getLogger('app')


def _extract_first_error_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return 'Ошибка валидации данных'

    first = errors[0]
    # Pydantic обычно кладёт текст ValueError сюда:
    msg = first.get('msg')
    if msg:
        return msg

    # Иногда текст может лежать глубже (на всякий случай)
    ctx = first.get('ctx') or {}
    if isinstance(ctx, dict) and ctx.get('error'):
        return str(ctx['error'])

    return 'Ошибка валидации данных'


def add_exception_handlers(app: FastAPI) -> None:
    """Добавляет обработчики Кастомных исключений в наше приложение."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        # Универсальный обработчик наших кастомных исключений
        body = CustomErrorResponse(
            code=int(exc.status_code),
            message=exc.message,
        ).model_dump()

        headers = None
        # Для 401 принято добавлять заголовок, чтобы понимать тип авторизации
        if exc.status_code == HTTPStatus.UNAUTHORIZED:
            headers = {'WWW-Authenticate': 'Bearer'}

        return JSONResponse(
            status_code=int(exc.status_code),
            content=body,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Это ошибки валидации данных:
        # 400 - если в запрос пришел невалидный JSON
        # 422 = если JSON валиден, но не проходит валидацию по схеме
        errors = exc.errors()
        # В зависимости от версии FastAPI/Pydantic может быть один из типов:
        is_json_decode_error = any(
            err.get('type') in ('json_invalid', 'value_error.jsondecode')
            for err in errors
        )

        if is_json_decode_error:
            body = CustomErrorResponse(
                code=HTTPStatus.BAD_REQUEST.value,
                message='Ошибка в параметрах запроса, проверьте JSON',
            ).model_dump()
            return JSONResponse(
                status_code=HTTPStatus.BAD_REQUEST.value,
                content=body,
            )

        logger.warning(
            'Validation error',
            extra={
                'path': str(request.url.path),
                'errors': exc.errors(),
                'body': exc.body,
            },
        )
        
        body = CustomErrorResponse(
            code=HTTPStatus.UNPROCESSABLE_ENTITY.value,
            message=_extract_first_error_message(exc),
        ).model_dump()
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY.value,
            content=body,
        )
