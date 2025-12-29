from functools import wraps
import logging
from typing import Any, Callable, TypeVar

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

    Пример:
        @cached('CAFES_LIST')
        async def get_cafes(show_all: bool = False):
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ttl = getattr(settings.cache, f'TTL_{ttl_key}')

            cache_key = key_function_result(func.__name__, *args, **kwargs)

            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f'Кэш-попадание: {func.__name__}')
                return cached_result

            result = await func(*args, **kwargs)

            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def cache_response(ttl_key: str) -> Callable[[F], F]:
    """Декоратор для кэширования HTTP-ответов FastAPI.

    Args:
        ttl_key: Ключ TTL из настроек (например, 'CAFES_LIST')

    Пример:
        @router.get("/cafes")
        @cache_response('CAFES_LIST')
        async def get_cafes(request: Request):
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            ttl = getattr(settings.cache, f'TTL_{ttl_key}')

            query_params = dict(request.query_params)
            cache_key = key_http_endpoint(
                method=request.method,
                path=request.url.path,
                query_params=query_params if query_params else None,
            )

            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f'HTTP кэш-попадание: {request.url.path}')
                return JSONResponse(
                    content=cached_result, headers={'X-Cache': 'HIT'},
                )

            result = await func(request, *args, **kwargs)

            if isinstance(result, JSONResponse):
                content = result.body
                if isinstance(content, bytes):
                    try:
                        content = orjson.loads(content)
                    except Exception:
                        return result
            else:
                content = result

            await cache.set(cache_key, content, ttl)

            if isinstance(result, JSONResponse):
                result.headers['X-Cache'] = 'MISS'
                return result
            return JSONResponse(
                content=content, headers={'X-Cache': 'MISS'},
            )

        return wrapper

    return decorator


def invalidate_cache(pattern_func: Callable[..., str]) -> Callable[[F], F]:
    """Декоратор для инвалидации кэша.

    Пример:
        @invalidate_cache(lambda cafe_id: f'cafe:{cafe_id}:*')
        async def update_cafe(cafe_id: UUID):
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            pattern = pattern_func(*args, **kwargs)
            deleted = await cache.delete_pattern(pattern)

            if deleted:
                logger.info(f'Инвалидирован кэш: {pattern}')

            return result

        return wrapper

    return decorator
