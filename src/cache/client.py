import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar

import orjson
from redis.asyncio import ConnectionPool, Redis

from src.config import settings


logger = logging.getLogger('app')
T = TypeVar('T')


def _json_dumps(value: Any) -> bytes:
    """Сериализует JSON-safe данные в bytes для хранения в Redis.

    Функция ожидает, что входные данные уже приведены к формату,
    совместимому с JSON. В проекте это гарантируется использованием
    Pydantic v2 и вызовом `model_dump(mode="json")` перед записью в кэш.

    Args:
        value: JSON-safe объект Python (dict, list, str, int и т.д.).

    Returns:
        Байтовое представление сериализованных данных.

    Example:
        >>> data = {'id': '123', 'active': True}
        >>> payload = _json_dumps(data)

    """
    return orjson.dumps(value)


class RedisCache:
    """Асинхронный клиент кэша Redis.

    Класс предоставляет инфраструктурный слой для работы с Redis и
    инкапсулирует:
    - управление пулом соединений
    - сериализацию и десериализацию данных
    - единообразное логирование операций
    - безопасную деградацию при недоступности Redis

    Кэш не содержит бизнес-логики и не выполняет преобразование доменных
    типов. Вся ответственность за подготовку JSON-safe данных лежит на
    уровне сервисов и схем.

    Example:
        >>> cache = RedisCache()
        >>> await cache.connect()
        >>> await cache.set('example:key', {'value': 1}, ttl=60)
        >>> data = await cache.get('example:key')

    """

    __slots__ = ('_client', '_pool')

    def __init__(self) -> None:
        """Инициализирует экземпляр RedisCache без активного соединения."""
        self._client: Optional[Redis] = None
        self._pool: Optional[ConnectionPool] = None

    async def connect(self) -> None:
        """Устанавливает соединение с Redis и инициализирует пул соединений.

        Использует настройки из конфигурации приложения. В случае ошибки
        соединение считается недоступным, и клиент продолжает работу
        в деградированном режиме.
        """
        try:
            self._pool = ConnectionPool.from_url(
                settings.redis.URL,
                password=settings.redis.PASSWORD or None,
                max_connections=settings.redis.MAX_CONNECTIONS,
                socket_connect_timeout=settings.redis.SOCKET_CONNECTION_TIMEOUT,
                socket_timeout=settings.redis.SOCKET_TIMEOUT,
                retry_on_timeout=settings.redis.RETRY_ON_TIMEOUT,
                decode_responses=False,
            )

            self._client = Redis(connection_pool=self._pool)
            await self._client.ping()

            logger.info(
                '✅ Redis подключен (pool: %d connections)',
                settings.redis.MAX_CONNECTIONS,
                extra={'user': 'SYSTEM'},
            )

        except Exception as e:
            logger.error(
                f'❌ Redis недоступен: {e}',
                extra={'user': 'SYSTEM'},
            )
            self._client = None
            self._pool = None

    async def close(self) -> None:
        """Корректно закрывает соединение с Redis и освобождает ресурсы."""
        if self._client:
            await self._client.aclose()
            self._client = None

        if self._pool:
            await self._pool.aclose()
            self._pool = None

        logger.info(
            'Redis connection closed',
            extra={'user': 'SYSTEM'},
        )

    @property
    def is_available(self) -> bool:
        """Проверяет доступность клиента Redis.

        Returns:
            True, если соединение с Redis установлено, иначе False.

        """
        return self._client is not None

    async def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша по ключу.

        Args:
            key: Ключ Redis.

        Returns:
            Десериализованные данные или None, если ключ отсутствует
            либо Redis недоступен.

        """
        if not self._client:
            logger.warning(
                'Redis GET skipped (client not available)',
                extra={'user': 'SYSTEM'},
            )
            return None

        try:
            raw = await self._client.get(key)

            if raw is None:
                logger.info(
                    f'Cache miss: {key}',
                    extra={'user': 'SYSTEM'},
                )
                return None

            logger.info(
                f'Cache hit: {key}',
                extra={'user': 'SYSTEM'},
            )
            return orjson.loads(raw)

        except Exception as e:
            logger.error(
                f'Redis GET error | key={key} | {e}',
                extra={'user': 'SYSTEM'},
            )
            return None

    async def set(self, key: str, value: Any, *, ttl: int) -> None:
        """Сохраняет значение в кэш с заданным временем жизни.

        Args:
            key: Ключ Redis.
            value: JSON-safe данные для сохранения.
            ttl: Время жизни записи в секундах.

        """
        if not self._client:
            logger.warning(
                'Redis SET skipped (client not available)',
                extra={'user': 'SYSTEM'},
            )
            return

        try:
            await self._client.set(
                key,
                _json_dumps(value),
                ex=ttl,
            )
            logger.info(
                f'Cache set: {key} (ttl={ttl}s)',
                extra={'user': 'SYSTEM'},
            )

        except Exception as e:
            logger.error(
                f'Redis SET error | key={key} | {e}',
                extra={'user': 'SYSTEM'},
            )

    async def delete(self, *keys: str) -> int:
        """Удаляет указанные ключи из кэша.

        Args:
            *keys: Один или несколько ключей Redis.

        Returns:
            Количество удалённых ключей.

        """
        if not self._client or not keys:
            return 0

        try:
            deleted = await self._client.delete(*keys)
            logger.info(
                f'Cache delete: {list(keys)} (deleted={deleted})',
                extra={'user': 'SYSTEM'},
            )
            return deleted

        except Exception as e:
            logger.error(
                f'Redis DELETE error | keys={keys} | {e}',
                extra={'user': 'SYSTEM'},
            )
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """Удаляет ключи, соответствующие заданному шаблону.

        Args:
            pattern: Redis-шаблон (например, "media:*").

        Returns:
            Количество удалённых ключей.

        """
        if not self._client:
            return 0

        deleted = 0
        try:
            async for key in self._client.scan_iter(match=pattern, count=100):
                deleted += await self._client.delete(key)

            logger.info(
                f'Cache delete by pattern: {pattern} (deleted={deleted})',
                extra={'user': 'SYSTEM'},
            )
            return deleted

        except Exception as e:
            logger.error(
                f'Redis DELETE PATTERN error | pattern={pattern} | {e}',
                extra={'user': 'SYSTEM'},
            )
            return deleted

    async def get_or_set(
        self,
        *,
        key: str,
        ttl: int,
        loader: Callable[[], Awaitable[T]],
    ) -> T:
        """Возвращает/загружает значение кэша и сохраняет его при отсутствии.

        Args:
            key: Ключ Redis.
            ttl: Время жизни значения в секундах.
            loader: Асинхронная функция загрузки данных.

        Returns:
            Значение из кэша или результат работы loader.

        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await loader()
        if value is not None:
            await self.set(key, value, ttl=ttl)

        return value


cache = RedisCache()


async def get_cache() -> RedisCache:
    """Возвращает singleton-экземпляр RedisCache.

    Используется для внедрения зависимости в сервисы и эндпоинты.

    Returns:
        Экземпляр RedisCache.

    """
    return cache
