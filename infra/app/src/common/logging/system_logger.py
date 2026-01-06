from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Union


logs_dir = Path('logs')
system_logs_dir = logs_dir / 'system'
system_logs_dir.mkdir(parents=True, exist_ok=True)


class SystemJsonFormatter(logging.Formatter):
    """JSON форматтер для структурированных системных логов."""

    def format(self, record: logging.LogRecord) -> str:
        """Преобразует запись лога в JSON объект с полной информацией.

        Содержит:
        - дата и время наступления события
        - уровень события
        - информация о пользователе (username и id или SYSTEM)
        - описание события с параметрами
        """
        log_entry: Dict[str, Any] = {
            'timestamp': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
            'level': record.levelname,
            'component': getattr(record, 'component', 'system'),
            'message': record.getMessage(),
        }

        user_id = getattr(record, 'user_id', None)
        username = getattr(record, 'username', None)

        if user_id or username:
            user_info: Dict[str, Any] = {}
            if username:
                user_info['username'] = username
            if user_id:
                user_info['id'] = user_id
            log_entry['user'] = user_info
        else:
            log_entry['user'] = 'SYSTEM'

        system_fields = [
            'operation',
            'model',
            'object_id',
            'endpoint',
            'table',
            'status_code',
            'response_time_ms',
            'execution_time',
        ]
        for field in system_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)

        # Информация об исключениях
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


system_logger = logging.getLogger('booking_system')
system_logger.setLevel(logging.INFO)
system_logger.propagate = False

# Хендлер для файла с ротацией
system_file_handler = RotatingFileHandler(
    system_logs_dir / 'system_events.log',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8',
)
system_file_handler.setFormatter(SystemJsonFormatter())

# Хендлер для консоли (используем простой формат)
system_console_handler = logging.StreamHandler()
system_console_formatter = logging.Formatter(
    fmt=(
        '%(asctime)s | SYSTEM | %(levelname)-8s | '
        '%(component)-12s | %(message)s'
    ),
    datefmt='%d-%m-%Y %H:%M:%S',
)
system_console_handler.setFormatter(system_console_formatter)

# Подключаем обработчики для централизованного логирования
system_logger.addHandler(system_file_handler)
system_logger.addHandler(system_console_handler)


def _format_user_for_log(
    user_id: Optional[Union[int, str]],
    username: Optional[str],
) -> Dict[str, Any]:
    """Подготавливает информацию о пользователе для логов."""
    extra_data: Dict[str, Any] = {'component': 'system'}

    if user_id is not None:
        extra_data['user_id'] = user_id
    if username is not None:
        extra_data['username'] = username

    return extra_data


def log_system_crud(
    operation: str,
    model: str,
    object_id: Optional[Any] = None,
    user_id: Optional[Union[int, str]] = None,
    username: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Логирует CRUD операции в системе.

    Соответствует ТЗ: "создана запись в таблице ... с параметрами ..."

    Параметры:
    - operation: тип операции (CREATE, READ, UPDATE, DELETE)
    - model: имя модели/таблицы данных
    - object_id: идентификатор объекта
    - user_id: идентификатор пользователя (число или строка) согласно ТЗ
    - username: имя пользователя согласно ТЗ
    - details: дополнительные параметры согласно ТЗ
    """
    # Формируем описание события
    description = f'{operation} {model}'
    if object_id:
        description += f' #{object_id}'
    # Формируем полное сообщение
    full_message = description
    if details:
        details_str = ', '.join(f'{k}={v}' for k, v in details.items())
        full_message += f' с параметрами: {details_str}'

    # Подготавливаем дополнительные данные
    extra_data = _format_user_for_log(user_id, username)
    extra_data.update({
        'component': 'crud',
        'operation': operation.lower(),
        'model': model,
    })

    if object_id is not None:
        extra_data['object_id'] = object_id
    if details:
        extra_data['details'] = details

    system_logger.info(full_message, extra=extra_data)


def log_system_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[Union[int, str]] = None,
    username: Optional[str] = None,
) -> None:
    """Логирует системные API запросы.

    Автоматически определяет уровень по статус-коду.
    """
    # Определяем уровень
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING
    else:
        level = logging.INFO

    # Формируем сообщение
    message = f'{method} {endpoint} → {status_code} ({duration_ms:.0f}ms)'

    # Дополнительные данные
    extra_data = _format_user_for_log(user_id, username)
    extra_data.update({
        'component': 'api',
        'endpoint': endpoint,
        'status_code': status_code,
        'response_time_ms': duration_ms,
    })

    system_logger.log(level, message, extra=extra_data)


def log_system_database(
    operation: str,
    table: Optional[str] = None,
    execution_time: Optional[float] = None,
    user_id: Optional[Union[int, str]] = None,
    username: Optional[str] = None,
) -> None:
    """Логирует системные события базы данных."""
    message = f'Database {operation}'
    if table:
        message += f' on {table}'

    extra_data = _format_user_for_log(user_id, username)
    extra_data.update({
        'component': 'database',
        'operation': operation,
    })

    if table:
        extra_data['table'] = table
    if execution_time:
        extra_data['execution_time'] = execution_time

    system_logger.info(message, extra=extra_data)


def log_system_error(
    context: str,
    error: Exception,
    user_id: Optional[Union[int, str]] = None,
    username: Optional[str] = None,
) -> None:
    """Логирует системные ошибки."""
    message = f'System error: {context}'

    extra_data = _format_user_for_log(user_id, username)
    extra_data.update({
        'component': 'error',
        'context': context,
    })

    system_logger.error(message, extra=extra_data, exc_info=True)


def log_system_event(
    description: str,
    level: str = 'INFO',
    user_id: Optional[Union[int, str]] = None,
    username: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Универсальная функция для логирования системных событий.

    Полностью соответствует требованиям ТЗ:
    - дата и время наступления события
    - уровень события (INFO, ERROR, WARNING и др.)
    - имя пользователя и его идентификатор. Если пользователя нет - SYSTEM
    - описание события с параметрами
    """
    # Формируем полное сообщение
    full_message = description
    if details:
        details_str = ', '.join(f'{k}={v}' for k, v in details.items())
        full_message += f' с параметрами: {details_str}'

    # Подготавливаем данные
    extra_data = _format_user_for_log(user_id, username)
    if details:
        extra_data['details'] = details

    # Определяем уровень
    log_levels = {
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    log_level = log_levels.get(level.upper(), logging.INFO)

    # Логируем
    system_logger.log(log_level, full_message, extra=extra_data)


def setup_uvicorn_system_logging() -> None:
    """Настраивает Uvicorn для логирования системных событий.

    Дополняет существующую конфигурацию, не заменяет её.
    """
    # Получаем логгеры Uvicorn
    uvicorn_logger = logging.getLogger('uvicorn')
    uvicorn_access = logging.getLogger('uvicorn.access')
    uvicorn_error = logging.getLogger('uvicorn.error')

    # Добавляем системные хендлеры к существующим
    for logger in [uvicorn_logger, uvicorn_access, uvicorn_error]:
        # Не очищаем существующие хендлеры, добавляем новые
        logger.addHandler(system_file_handler)
        logger.propagate = True  # Позволяем пропагацию


def initialize_system_logging() -> None:
    """Инициализирует системное логирование при запуске приложения."""
    log_system_event(
        'Системное логирование инициализировано',
        user_id='SYSTEM',
        username='SYSTEM',
    )
