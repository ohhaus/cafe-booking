import logging
from typing import Union

import orjson
from redis.asyncio import ConnectionPool, Redis

from src.config import settings


logger = logging.getLogger('app')


class RedisCache:
    """Асинхронный Redis клиент с connection pooling."""

    def __init__(self) -> None:
        """Инициализация Redis клиента."""
        self._client: Redis | None = None
        self._pool: ConnectionPool | None = None

    async def connect(self) -> None:
        """Подключаемся к Redis с connection pool."""
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
            )
        except Exception as e:
            logger.warning(f'⚠️ Redis недоступен: {e}')
            self._client = None
            self._pool = None

    async def close(self) -> None:
        """Закрываем соединение и пул."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.aclose()
            self._pool = None
        logger.info('Redis connection closed')

    @property
    def is_available(self) -> bool:
        """Проверка доступности Redis."""
        return self._client is not None

    async def get(
        self,
        key: str,
    ) -> Union[dict, list, str, int, float, bool, None]:
        """Берём данные из кэша. Если что-то не так - возвращаем None."""
        if not self.is_available:
            return None

        try:
            data = await self._client.get(key)
            return orjson.loads(data) if data else None
        except Exception as e:
            logger.debug(f'Cache get error for key {key}: {e}')
            return None

    async def set(
        self,
        key: str,
        value: Union[dict, list, str, int, float, bool],
        ttl: int = 300,
    ) -> bool:
        """Сохраняем данные в кэш. Возвращает True если успешно."""
        if not self.is_available:
            return False

        try:
            data = orjson.dumps(value)
            await self._client.setex(key, ttl, data)
            return True
        except Exception as e:
            logger.debug(f'Cache set error for key {key}: {e}')
            return False

    async def delete(self, *keys: str) -> int:
        """Удаляем ключи. Возвращаем количество удалённых."""
        if not self.is_available or not keys:
            return 0

        try:
            return await self._client.delete(*keys)
        except Exception as e:
            logger.debug(f'Cache delete error: {e}')
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """Удаляем ключи по паттерну (batch delete для production)."""
        if not self.is_available:
            return 0

        try:
            deleted = 0
            batch_size = 100
            keys_batch = []

            async for key in self._client.scan_iter(
                match=pattern,
                count=batch_size,
            ):
                keys_batch.append(key)
                if len(keys_batch) >= batch_size:
                    deleted += await self._client.delete(*keys_batch)
                    keys_batch = []

            if keys_batch:
                deleted += await self._client.delete(*keys_batch)

            return deleted
        except Exception as e:
            logger.debug(f'Cache delete_pattern error for {pattern}: {e}')
            return 0

    async def exists(self, *keys: str) -> int:
        """Проверяем существование ключей."""
        if not self.is_available or not keys:
            return 0

        try:
            return await self._client.exists(*keys)
        except Exception:
            return 0


cache = RedisCache()


async def get_cache() -> RedisCache:
    """DI для внедрения кэша в эндпоинты."""
    return cache
