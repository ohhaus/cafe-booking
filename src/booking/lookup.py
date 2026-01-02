from typing import Awaitable, Callable, Iterable, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.cache import keys
from src.cache.client import RedisCache
from src.cafes.crud import cafe_crud
from src.config import settings
from src.slots.crud import slot_crud
from src.slots.models import Slot
from src.tables.crud import table_crud
from src.tables.models import Table


def _cached_active_to_bool(value: object) -> bool | None:
    """Преобразует кэшированное значение активности в булево.

    Redis хранит значения как JSON, поэтому значение может быть:
    - None — нет в кэше
    - int (0/1) — старый формат
    - bool — текущий формат

    Args:
        value: Значение из кэша (None, int, bool)

    Returns:
        bool: True/False, если значение валидно, иначе None.

    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        return None
    return None


def _negative_ttl(positive_ttl: int) -> int:
    """Возвращает TTL для негативного кэширования.

    Если задан `TTL_NEGATIVE` в настройках — использует его.
    Иначе — возвращает короткое значение, чтобы "отрицание" быстро протухало.

    Args:
        positive_ttl: TTL для положительного кэширования.

    Returns:
        int: TTL для негативного кэширования.

    """
    ttl = getattr(settings.cache, 'TTL_NEGATIVE', None)
    if isinstance(ttl, int) and ttl > 0:
        return ttl
    return max(5, min(60, positive_ttl // 10))


async def _bulk_existing_active_with_negative_cache(
    *,
    client_cache: RedisCache,
    ids: Iterable[UUID],
    make_key: Callable[[UUID], str],
    positive_ttl: int,
    fetch_existing_active: Callable[[Set[UUID]], Awaitable[Set[UUID]]],
) -> Set[UUID]:
    """Массовая проверка существования активных объектов с кэшированием.

    Применяет негативное кэширование для неактивных объектов.
    Проверяет каждую сущность по ID:
    - Если в кэше значение `1`/`true` → считается активной.
    - Если `0`/`false` → неактивной, результат кэшируется на короткое время
    (TTL_NEGATIVE).
    - Если нет в кэше → запрашивается через loader из БД, результат кэшируется.

    Используется для кафе, столов и слотов, чтобы минимизировать запросы к БД.

    Args:
        client_cache: Клиент Redis для кэширования.
        ids: Список ID сущностей для проверки.
        make_key: Функция, создающая ключ кэша по ID.
        positive_ttl: TTL для положительного результата (сущность существует).
        fetch_existing_active: Асинхронная функция, возвращающая множество
            существующих и активных ID.

    Returns:
        Множество ID, которые существуют и активны.

    """
    ids_set = set(ids)
    if not ids_set:
        return set()

    present: Set[UUID] = set()  # Уже активные в кэше
    missed: Set[UUID] = set()  # Не в кэше или неактивные

    for _id in ids_set:
        cached = await client_cache.get(make_key(_id))
        val = _cached_active_to_bool(cached)
        if val is None:
            missed.add(_id)  # Нет в кэше → нужно проверить в БД
        elif val is True:  # noqa
            present.add(_id)  # Есть в кэше и активен → сразу добавляем
        # val is False → неактивен → игнорируем

    if not missed:
        return present

    found = await fetch_existing_active(missed)
    present |= found  # Объединяем IDs (из кэша) и IDs (из БД)

    neg_ttl = _negative_ttl(positive_ttl)

    for _id in missed:
        is_present = _id in found
        await client_cache.set(
            make_key(_id),
            1 if is_present else 0,
            ttl=positive_ttl if is_present else neg_ttl,
        )

    return present


async def cafe_is_active(
    session: AsyncSession,
    client_cache: RedisCache,
    cafe_id: UUID,
) -> bool:
    """Проверяет, существует ли активное кафе с заданным ID.

    Использует кэширование с TTL из `CacheSettings.TTL_CAFE_ACTIVE`.

    Args:
        session: Асинхронная сессия БД.
        client_cache: Клиент Redis.
        cafe_id: ID кафе.

    Returns:
        bool: True, если кафе существует и активно.

    """
    key = keys.key_cafe_active(cafe_id)

    async def loader() -> int:
        return (
            1
            if await cafe_crud.exists(session, id=cafe_id, active=True)
            else 0
        )

    cached = await client_cache.get_or_set(
        key=key,
        ttl=settings.cache.TTL_CAFE_ACTIVE,
        loader=loader,
    )
    return bool(_cached_active_to_bool(cached))


async def tables_existing_active_in_cafe(
    session: AsyncSession,
    client_cache: RedisCache,
    cafe_id: UUID,
    table_ids: Iterable[UUID],
) -> Set[UUID]:
    """Проверяет, какие столы существуют, активны и принадлежат кафе.

    Использует кэш и массовую проверку с негативным кэшированием.

    Args:
        session: Асинхронная сессия БД.
        client_cache: Клиент Redis.
        cafe_id: ID кафе.
        table_ids: Список ID столов для проверки.

    Returns:
        Множество ID столов, которые активны и принадлежат кафе.

    """

    async def fetch(missed: Set[UUID]) -> Set[UUID]:
        rows = await table_crud.get_multi(
            session=session,
            filters=[
                Table.id.in_(missed),
                Table.cafe_id == cafe_id,
                Table.active.is_(True),
            ],
        )
        return {table.id for table in rows}

    return await _bulk_existing_active_with_negative_cache(
        client_cache=client_cache,
        ids=table_ids,
        make_key=lambda tid: keys.key_cafe_table_active(cafe_id, tid),
        positive_ttl=settings.cache.TTL_CAFE_TABLE_ACTIVE,
        fetch_existing_active=fetch,
    )


async def slots_existing_active_in_cafe(
    session: AsyncSession,
    client_cache: RedisCache,
    cafe_id: UUID,
    slot_ids: Iterable[UUID],
) -> Set[UUID]:
    """Проверяет, какие слоты существуют, активны и принадлежат кафе.

    Использует кэш и массовую проверку с негативным кэшированием.

    Args:
        session: Асинхронная сессия БД.
        client_cache: Клиент Redis.
        cafe_id: ID кафе.
        slot_ids: Список ID слотов для проверки.

    Returns:
        Множество ID слотов, которые активны и принадлежат кафе.

    """

    async def fetch(missed: Set[UUID]) -> Set[UUID]:
        rows = await slot_crud.get_multi(
            session=session,
            filters=[
                Slot.id.in_(missed),
                Slot.cafe_id == cafe_id,
                Slot.active.is_(True),
            ],
        )
        return {slot.id for slot in rows}

    return await _bulk_existing_active_with_negative_cache(
        client_cache=client_cache,
        ids=slot_ids,
        make_key=lambda sid: keys.key_cafe_slot_active(cafe_id, sid),
        positive_ttl=settings.cache.TTL_CAFE_SLOT_ACTIVE,
        fetch_existing_active=fetch,
    )
