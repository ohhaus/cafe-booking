# src/common/exception_handlers.py
"""Обработчики исключений для FastAPI приложения."""
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.common.exceptions import AppException
from src.common.schemas import CustomErrorResponse


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        # Универсальный обработчик наших кастомных исключений
        body = CustomErrorResponse(
            code=exc.code.value,
            message=exc.message,
            ).model_dump()

        headers = None
        # Для 401 принято добавлять заголовок, чтобы понимать тип авторизации
        if exc.status_code == HTTPStatus.UNAUTHORIZED:
            headers = {"WWW-Authenticate": "Bearer"}

        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=headers,
            )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Это ошибки валидации данных 422
        body = CustomErrorResponse(
            code=HTTPStatus.UNPROCESSABLE_ENTITY.value,
            message='Ошибка валидации данных',
            ).model_dump()
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=body)
