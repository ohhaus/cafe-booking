from functools import wraps
import logging
from typing import Any, Callable, TypeVar, Union

from fastapi import Request
from fastapi.responses import JSONResponse
import orjson

from src.config import settings

from .client import cache
from .keys import key_function_result, key_http_endpoint


logger = logging.getLogger('app.cache')
F = TypeVar('F', bound=Callable[..., Any])


def cached(ttl_key: str) -> Callable[[F], F]:
    """Декоратор для кэширования результатов функций.

    Args:
        ttl_key: Ключ TTL из настроек (например, 'CAFES_LIST')

    Example:
        @cached('CAFES_LIST')
        async def get_cafes(show_all: bool = False):
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Получаем TTL из настроек
            ttl = getattr(settings.cache, f'TTL_{ttl_key}')
            cache_key = key_function_result(func.__name__, *args, **kwargs)

            # Пытаемся получить из кэша
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f'✓ Cache HIT: {func.__name__}')
                return cached_result

            # Выполняем функцию
            logger.debug(f'✗ Cache MISS: {func.__name__}')
            result = await func(*args, **kwargs)

            # Сохраняем в кэш
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def cache_endpoint(ttl_key: str) -> Callable[[F], F]:
    """Декоратор для кэширования HTTP-ответов FastAPI эндпоинтов.

    Упрощенная версия - работает только с dict/list результатами.

    Args:
        ttl_key: Ключ TTL из настроек (например, 'CAFES_LIST')

    Example:
        @router.get("/cafes")
        @cache_endpoint('CAFES_LIST')
        async def get_cafes(request: Request, db: AsyncSession = Depends(...)):
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(
            request: Request,
            *args: Any,
            **kwargs: Any,
        ) -> JSONResponse:
            ttl = getattr(settings.cache, f'TTL_{ttl_key}')

            # Генерируем ключ кэша
            query_params = dict(request.query_params)
            cache_key = key_http_endpoint(
                method=request.method,
                path=request.url.path,
                query_params=query_params if query_params else None,
            )

            # Проверяем кэш
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    f'✓ HTTP Cache HIT: {request.method} {request.url.path}',
                )
                return JSONResponse(
                    content=cached_result,
                    headers={'X-Cache': 'HIT'},
                )

            # Выполняем оригинальную функцию
            logger.debug(
                f'✗ HTTP Cache MISS: {request.method} {request.url.path}',
            )
            result = await func(request, *args, **kwargs)

            # Определяем контент для кэширования
            if isinstance(result, JSONResponse):
                # Если это JSONResponse, извлекаем body
                content = orjson.loads(result.body)
            elif isinstance(result, (dict, list)):
                # Если dict/list - используем напрямую
                content = result
            else:
                # Для других типов - не кэшируем
                logger.warning(f'Cannot cache response type: {type(result)}')
                return result

            # Сохраняем в кэш
            await cache.set(cache_key, content, ttl)

            # Возвращаем с заголовком
            if isinstance(result, JSONResponse):
                result.headers['X-Cache'] = 'MISS'
                return result

            return JSONResponse(content=content, headers={'X-Cache': 'MISS'})

        return wrapper

    return decorator


def auto_invalidate(
    *patterns_or_funcs: Union[str, Callable[..., str]],
) -> Callable[[F], F]:
    """Декоратор для автоматической инвалидации кэша после выполнения функции.

    Поддерживает как строки-паттерны, так и функции для генерации паттернов.

    Args:
        patterns_or_funcs: Паттерны (str) или функции для генерации паттернов

    Example:
        # Статический паттерн
        @auto_invalidate('cafes:*')
        async def create_cafe(...):
            ...

        # Динамический паттерн с функцией
        @auto_invalidate(lambda cafe_id: f'cafe:{cafe_id}:*')
        async def update_cafe(cafe_id: UUID, ...):
            ...

        # Несколько паттернов
        @auto_invalidate('cafes:*', lambda cafe_id: f'cafe:{cafe_id}:*')
        async def update_cafe(cafe_id: UUID, ...):
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Выполняем оригинальную функцию
            result = await func(*args, **kwargs)

            # Инвалидируем кэш
            for pattern_or_func in patterns_or_funcs:
                if callable(pattern_or_func):
                    # Если это функция - вызываем с аргументами
                    pattern = pattern_or_func(*args, **kwargs)
                else:
                    # Если строка - используем как есть
                    pattern = pattern_or_func

                deleted = await cache.delete_pattern(pattern)
                if deleted:
                    logger.info(
                        f'Invalidated cache: {pattern} ({deleted} keys)',
                    )

            return result

        return wrapper

    return decorator


def conditional_cache(
    ttl_key: str,
    condition: Callable[..., bool],
) -> Callable[[F], F]:
    """Декоратор для условного кэширования (кэшируем если condition=True).

    Args:
        ttl_key: Ключ TTL из настроек
        condition: Функция для проверки условия кэширования

    Example:
        @conditional_cache('CAFES_LIST', lambda show_all: not show_all)
        async def get_cafes(show_all: bool = False):
            # Кэшируем только если show_all=False
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            should_cache = condition(*args, **kwargs)

            if not should_cache:
                return await func(*args, **kwargs)

            # Если условие выполнено - применяем обычное кэширование
            ttl = getattr(settings.cache, f'TTL_{ttl_key}')
            cache_key = key_function_result(func.__name__, *args, **kwargs)

            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f'✓ Conditional cache HIT: {func.__name__}')
                return cached_result

            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
