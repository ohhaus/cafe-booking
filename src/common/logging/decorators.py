import functools
import inspect
from typing import Any, Callable

from src.common.logging.config import logger


def _extract_user(kwargs: dict[str, Any]) -> str:
    """Извлекает и форматирует пользователя из kwargs.

    Args:
        kwargs: Аргументы функции

    Returns:
        Строковое представление пользователя

    """
    user_obj = kwargs.get('current_user')

    if user_obj and hasattr(user_obj, 'username') and hasattr(user_obj, 'id'):
        from src.auth.models import UserRole

        role_str = (
            UserRole(user_obj.role).name
            if user_obj.role is not None
            else 'SYSTEM'
        )
        return f'{role_str} {user_obj.username}({user_obj.id})'

    return 'SYSTEM'


def _extract_params(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Обрабатывает параметры, исключая чувствительные и ненужные ключи.

    Args:
        kwargs: Аргументы функции

    Returns:
        Отфильтрованные параметры

    """
    exclude_keys = {
        'current_user',
        'session',
        'credentials',
        '__fastapi_cache_request',
        '__fastapi_cache_response',
    }
    sensitive_fields = {'password', 'token', 'secret'}

    params = {}

    for k, v in kwargs.items():
        if k in exclude_keys:
            continue

        # Обработка Pydantic моделей
        if hasattr(v, 'model_dump'):
            # Pydantic v2
            model_dict = v.model_dump(exclude_none=True)
            params[k] = {
                field: '[FILTERED]' if field in sensitive_fields else value
                for field, value in model_dict.items()
            }
        elif hasattr(v, 'dict') and callable(getattr(v, 'dict', None)):
            # Pydantic v1
            model_dict = v.dict(exclude_none=True)
            params[k] = {
                field: '[FILTERED]' if field in sensitive_fields else value
                for field, value in model_dict.items()
            }
        else:
            params[k] = v

    return params


def _log_start(action: str, user: str, params: dict[str, Any]) -> None:
    """Логирует запуск процесса.

    Args:
        action: Название действия
        user: Пользователь
        params: Параметры

    """
    msg = f'Запуск 🚀 {action}' + (f' | параметры: {params}' if params else '')
    logger.info(msg, extra={'user': user})


def _log_success(action: str, user: str) -> None:
    """Логирует успешное завершение процесса.

    Args:
        action: Название действия
        user: Пользователь

    """
    logger.info(f'Успешно ✅ {action}', extra={'user': user})


def _log_error(action: str, user: str, error: Exception) -> None:
    """Логирует неуспешное завершение процесса.

    Args:
        action: Название действия
        user: Пользователь
        error: Исключение

    """
    logger.error(
        f'Неудача ❌ {action} | {str(error)}',
        extra={'user': user},
    )


def log_action(
    action: str,
    skip_logging: bool = False,
    only_errors: bool = False,
) -> Callable:
    """Декоратор для логирования процессов.

    Используется для логирования операций в service layer.

    Args:
        action: Описание действия для лога
        skip_logging: Пропустить логирование старта и успеха
        only_errors: Логировать только ошибки

    Returns:
        Декоратор функции

    Example:
        @log_action('Создание пользователя')
        async def create_user(
            self,
            session: AsyncSession,
            *,
            obj_in: UserCreate,
            current_user: User,
        ) -> User:
            ...

    """

    def wrapper(func: Callable) -> Callable:
        """Возвращает асинхронную или синхронную обертку.

        Результат зависит от типа оборачиваемой функции.
        """
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_inner(*args: Any, **kwargs: Any) -> Any:
            """Обертка для асинхронной функции."""
            user = _extract_user(kwargs)
            params = _extract_params(kwargs)

            if not skip_logging and not only_errors:
                _log_start(action, user, params)

            try:
                result = await func(*args, **kwargs)
                if not skip_logging and not only_errors:
                    _log_success(action, user)
                return result
            except Exception as e:
                _log_error(action, user, e)
                raise

        @functools.wraps(func)
        def sync_inner(*args: Any, **kwargs: Any) -> Any:
            """Обертка для синхронной функции."""
            user = _extract_user(kwargs)
            params = _extract_params(kwargs)

            if not skip_logging and not only_errors:
                _log_start(action, user, params)

            try:
                result = func(*args, **kwargs)
                if not skip_logging and not only_errors:
                    _log_success(action, user)
                return result
            except Exception as e:
                _log_error(action, user, e)
                raise

        return async_inner if is_async else sync_inner

    return wrapper
