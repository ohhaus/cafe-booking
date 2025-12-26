"""ОБщие ответы сервера 4хх статуса."""

from http import HTTPStatus

from src.common.responses import error_response


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
ERROR_422 = error_response(
    HTTPStatus.UNPROCESSABLE_ENTITY,
    'Ошибка валидации данных',
)
