"""Кастомные исключения для проекта."""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Optional


@dataclass(eq=False)
class AppException(Exception):
    """Базовое исключение приложения.

    Все кастомные исключения наследуются от этого класса.
    Позволяет единообразно возвращать ошибки в формате:
    {
        "code": <internal_code>,
        "message": <human_readable_message>
    }
    с соответствующим HTTP-статусом.
    """

    status_code: HTTPStatus  # HTTP статус ответа
    code: Optional[int]  # внутренний/доменный код
    message: str

    def __init__(
        self,
        *,
        status_code: HTTPStatus,
        message: str,
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует базовое исключение приложения.

        Args:
            status_code: HTTP статус ответа
            message: Человекочитаемое сообщение об ошибке
            code: Внутренний код ошибки (по умолчанию совпадает с status_code)

        """
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotAuthorizedException(AppException):
    """Исключение: пользователь не авторизован.

    Вызывается при отсутствии или невалидности токена.
    (HTTP 401 Unauthorized)
    """

    def __init__(
        self,
        message: str = 'Неавторизированный пользователь',
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует исключение неавторизованного доступа.

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки

        """
        super().__init__(
            status_code=HTTPStatus.UNAUTHORIZED,
            message=message,
            code=code,
        )


class ValidationErrorException(AppException):
    """Исключение: ошибка валидации входных данных.

    Возникает при неверном формате или значении параметров запроса.
    (HTTP 422 Unprocessable Entity)
    """

    def __init__(
        self,
        message: str = 'Ошибка валидации данных',
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует исключение валидации данных.

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки

        """
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            message=message,
            code=code,
        )


class ForbiddenException(AppException):
    """Исключение: доступ запрещён.

    Пользователь авторизован, но не имеет прав на действие.
    (HTTP 403 Forbidden)
    """

    def __init__(
        self,
        message: str = 'Доступ запрещен',
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует исключение запрещённого доступа.

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки

        """
        super().__init__(
            status_code=HTTPStatus.FORBIDDEN,
            message=message,
            code=code,
        )


class NotFoundException(AppException):
    """Исключение: запрашиваемый ресурс не найден.

    Объект с указанным ID не существует.
    (HTTP 404 Not Found)
    """

    def __init__(
        self,
        message: str = 'Данные не найдены',
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует исключение "не найдено".

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки

        """
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            message=message,
            code=code,
        )


class BadRequestException(AppException):
    """Исключение: некорректный запрос.

    Ошибка в синтаксисе или параметрах запроса (например, невалидный JSON).
    (HTTP 400 Bad Request)
    """

    def __init__(
        self,
        message: str = 'Ошибка в параметрах запроса',
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует исключение "некорректный запрос".

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки

        """
        super().__init__(
            status_code=HTTPStatus.BAD_REQUEST,
            message=message,
            code=code,
        )


class ConflictException(AppException):
    """Исключение: конфликт данных.

    Операция нарушает уникальность или целостность (например,
    дублирующая бронь).
    (HTTP 409 Conflict)
    """

    def __init__(
        self,
        message: str = 'Конфликт данных',
        code: Optional[int] = None,
    ) -> None:
        """Инициализирует исключение конфликта данных.

        Args:
            message: Сообщение об ошибке
            code: Внутренний код ошибки

        """
        super().__init__(
            status_code=HTTPStatus.CONFLICT,
            message=message,
            code=code,
        )
