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
    """Ошибка неавторизированного пользователя."""

    def __init__(
            self,
            message: str = 'Неавторизированный пользователь',
    ) -> None:
        """Инициализирует ошибку неавторизированного пользователя."""
        super().__init__(
            status_code=HTTPStatus.UNAUTHORIZED,
            code=HTTPStatus.UNAUTHORIZED,
            message=message)


class ValidationErrorException(AppException):
    """Ошибка валидации данных."""

    def __init__(self, message: str = "Ошибка валидации данных") -> None:
        """Инициализирует ошибку валидации данных."""
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=HTTPStatus.UNPROCESSABLE_ENTITY,
            message=message)


class ForbiddenException(AppException):
    """Ошибка доступа запрещен."""

    def __init__(self, message: str = "Доступ запрещен") -> None:
        """Инициализирует ошибку доступа запрещен."""
        super().__init__(
            status_code=HTTPStatus.FORBIDDEN,
            code=HTTPStatus.FORBIDDEN,
            message=message)


class NotFoundException(AppException):
    """Ошибка данных не найдены."""

    def __init__(self, message: str = "Данные не найдены") -> None:
        """Инициализирует ошибку данных не найдены."""
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            code=HTTPStatus.NOT_FOUND,
            message=message)


class BadRequestException(AppException):
    """Ошибка в параметрах запроса."""

    def __init__(self, message: str = "Ошибка в параметрах запроса") -> None:
        """Инициализирует ошибку запроса (HTTP 400)."""
        super().__init__(
            status_code=HTTPStatus.BAD_REQUEST,
            code=HTTPStatus.BAD_REQUEST,
            message=message,
        )
