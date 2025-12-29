# src/common/exceptions.py
"""Кастомные исключения для проекта."""
from dataclasses import dataclass
from http import HTTPStatus


@dataclass
class AppException(Exception):
    """Базовое исключение приложения."""

    status_code: int
    code: int
    message: str


class NotAuthorizedException(AppException):
    def __init__(self, message: str = "Неавторизированный пользователь"):
        super().__init__(
            status_code=HTTPStatus.UNAUTHORIZED,
            code=HTTPStatus.UNAUTHORIZED,
            message=message)


class ValidationErrorException(AppException):
    def __init__(self, message: str = "Ошибка валидации данных"):
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=HTTPStatus.UNPROCESSABLE_ENTITY,
            message=message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Доступ запрещен"):
        super().__init__(
            status_code=HTTPStatus.FORBIDDEN,
            code=HTTPStatus.FORBIDDEN,
            message=message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Данные не найдены"):
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            code=HTTPStatus.NOT_FOUND,
            message=message)
