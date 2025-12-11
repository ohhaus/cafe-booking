from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config import settings


def create_db_engine(connection_string: str) -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy с конфигурацией пула соединений.

    Параметры пула (таймауты, размер, переиспользование) берутся из настроек.
    Поддерживает автоматический ping для проверки валидности соединений.

    Args:
        connection_string: Строка подключения к БД в формате SQLAlchemy URL.

    Returns:
        AsyncEngine: Асинхронный движок SQLAlchemy, готовый к использованию.

    Raises:
        ArgumentError: При невалидной строке подключения.
        SQLAlchemyError: При ошибках создания движка.

    """
    url = make_url(connection_string)

    timeout_kwargs = {
        'pool_timeout': settings.database.POOL_TIMEOUT,
        'pool_recycle': settings.database.POOL_RECYCLE,
        'pool_size': settings.database.POOL_SIZE,
        'max_overflow': settings.database.MAX_OVERFLOW,
        'pool_pre_ping': settings.database.POOL_PING,
    }

    return create_async_engine(url, **timeout_kwargs)


engine = create_db_engine(settings.database.URL)
