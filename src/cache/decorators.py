"""Декораторы для кэширования и инвалидации.

Декораторы:
    @cached - кэширование результатов функций
    @auto_invalidate - автоматическая инвалидация после выполнения
    @conditional_cache - условное кэширование

Примеры:
    @cached('CAFES_LIST')
    async def get_cafes_list():
        ...

    @auto_invalidate(pattern_all_cafes())
    async def create_cafe(...):
        ...

    @auto_invalidate(
        pattern_all_dishes(),
        lambda dish_id: key_dish(dish_id),
    )
    async def update_dish(dish_id: UUID, ...):
        ...
"""

from functools import wraps
import logging
from typing import Any, Callable, TypeVar, Union

from src.cache.client import cache
from src.cache.keys import key_function_result
from src.config import settings


logger = logging.getLogger('app.cache')
F = TypeVar('F', bound=Callable[..., Any])


def cached(ttl_key: str) -> Callable[[F], F]:
    """Декоратор для кэширования результатов функций.

    Автоматически генерирует ключ кэша на основе имени функции
    и её аргументов. Подходит для service-layer функций.

    Args:
        ttl_key: Ключ TTL из настроек (например, 'CAFES_LIST')

    Returns:
        Декорированная функция с кэшированием

    Example:
        >>> @cached('CAFES_LIST')
        ... async def get_cafes(show_all: bool = False):
        ...     # SELECT * FROM cafes ...
        ...     return cafes

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Получаем TTL из настроек
            ttl = getattr(settings.cache, f'TTL_{ttl_key}')
            cache_key = key_function_result(
                func.__name__,
                *args,
                **kwargs,
            )

            # Пытаемся получить из кэша
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.info(f'✓ Cache HIT: {func.__name__}')
                return cached_result

            # Выполняем функцию
            logger.info(f'✗ Cache MISS: {func.__name__}')
            result = await func(*args, **kwargs)

            # Сохраняем в кэш
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def auto_invalidate(
    *patterns_or_funcs: Union[str, Callable[..., str]],
) -> Callable[[F], F]:
    """Декоратор для автоматической инвалидации кэша.

    Инвалидирует кэш после успешного выполнения функции.
    Поддерживает как статические паттерны, так и динамические
    (через lambda функции).

    Args:
        *patterns_or_funcs: Паттерны (str) или функции для
            генерации паттернов

    Returns:
        Декорированная функция с автоинвалидацией

    Example:
        >>> # Статический паттерн
        >>> @auto_invalidate(pattern_all_cafes())
        ... async def create_cafe(...):
        ...     ...

        >>> # Динамический паттерн
        >>> @auto_invalidate(
        ...     pattern_all_dishes(),
        ...     lambda dish_id: key_dish(dish_id),
        ... )
        ... async def update_dish(dish_id: UUID, ...):
        ...     ...

        >>> # Множественная инвалидация
        >>> @auto_invalidate(
        ...     pattern_all_cafes(),
        ...     lambda cafe_id: key_cafe_pattern(cafe_id),
        ... )
        ... async def delete_cafe(cafe_id: UUID, ...):
        ...     ...

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
                    try:
                        pattern = pattern_or_func(*args, **kwargs)
                    except TypeError:
                        # Если lambda требует именованные аргументы
                        pattern = pattern_or_func(**kwargs)
                else:
                    # Если строка - используем как есть
                    pattern = pattern_or_func

                deleted = await cache.delete_pattern(pattern)
                if deleted:
                    logger.info(
                        f'✓ Invalidated: {pattern} ({deleted} keys)',
                    )

            return result

        return wrapper

    return decorator


def conditional_cache(
    ttl_key: str,
    condition: Callable[..., bool],
) -> Callable[[F], F]:
    """Декоратор для условного кэширования.

    Кэширует результат только если condition возвращает True.
    Полезно для кэширования с учётом параметров запроса.

    Args:
        ttl_key: Ключ TTL из настроек
        condition: Функция для проверки условия кэширования

    Returns:
        Декорированная функция с условным кэшированием

    Example:
        >>> # Кэшируем только если show_all=False
        >>> @conditional_cache(
        ...     'CAFES_LIST',
        ...     lambda show_all: not show_all,
        ... )
        ... async def get_cafes(show_all: bool = False): ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            should_cache = condition(*args, **kwargs)

            if not should_cache:
                return await func(*args, **kwargs)

            ttl = getattr(settings.cache, f'TTL_{ttl_key}')
            cache_key = key_function_result(
                func.__name__,
                *args,
                **kwargs,
            )

            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    f'✓ Conditional cache HIT: {func.__name__}',
                )
                return cached_result

            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
