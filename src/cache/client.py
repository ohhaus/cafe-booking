import logging
from typing import Union

import orjson
from redis.asyncio import Redis

from src.config import settings


logger = logging.getLogger('app.cache')


class RedisCache:
    """Асинхронный Redis клиент. Работает или не работает."""

    def __init__(self) -> None:
        """Инициализация Redis клиента."""
        self._client: Redis | None = None

    async def connect(self) -> None:
        """Подключаемся к Redis. Если не вышло - не страшно."""
        try:
            self._client = Redis.from_url(
                settings.redis.URL,
                password=settings.redis.PASSWORD or None,
                decode_responses=False,
            )
            await self._client.ping()
            logger.info('✅ Redis подключен')
        except Exception as e:
            logger.warning(f'⚠️ Redis недоступен: {e}')
            self._client = None

    async def close(self) -> None:
        """Закрываем соединение если оно есть."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(
        self, key: str,
    ) -> Union[dict, list, str, int, float, bool, None]:
        """Берём данные из кэша. Если что-то не так - возвращаем None."""
        if not self._client:
            return None

        try:
            data = await self._client.get(key)
            return orjson.loads(data) if data else None
        except Exception:
            return None

    async def set(
        self,
        key: str,
        value: Union[dict, list, str, int, float, bool],
        ttl: int = 300,
    ) -> None:
        """Сохраняем данные в кэш. Если не вышло - не страшно."""
        if not self._client:
            return

        try:
            data = orjson.dumps(value)
            await self._client.setex(key, ttl, data)
        except Exception:
            pass

    async def delete(self, *keys: str) -> int:
        """Удаляем ключи. Возвращаем количество удалённых."""
        if not self._client or not keys:
            return 0

        try:
            return await self._client.delete(*keys)
        except Exception:
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """Удаляем ключи по паттерну."""
        if not self._client:
            return 0

        try:
            deleted = 0
            async for key in self._client.scan_iter(match=pattern):
                await self._client.delete(key)
                deleted += 1
            return deleted
        except Exception:
            return 0


cache = RedisCache()


async def get_cache() -> RedisCache:
    """DI для внедрения кэша в эндпоинты."""
    return cache
