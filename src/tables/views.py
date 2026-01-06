import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.client import RedisCache, get_cache
from src.cache.keys import (
    key_cafe_table,
    key_cafe_tables,
)
from src.cafes.cafe_scoped import (
    ensure_cafe_exists_cached,
)
from src.cafes.cafes_help_caches import (
    cache_get_list,
    cache_get_one,
    cache_set,
    dump_list,
    dump_one,
    invalidate_tables_cache,
)
from src.cafes.service import ensure_manager_can_cud_cafe, is_admin_or_manager
from src.common.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationErrorException,
)
from src.config import settings
from src.database.sessions import get_async_session
from src.tables.crud import table_crud
from src.tables.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.tables.schemas import (
    TableCreate,
    TableUpdate,
    TableWithCafeInfo,
)
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.get(
    '/{cafe_id}/tables',
    response_model=list[TableWithCafeInfo],
    summary='Получение списка столов в кафе',
    description=(
        'Получение списка доступных для бронирования столов в кафе. '
        'Для администраторов и менеджеров - все столы '
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,
)
async def get_tables(
    cafe_id: UUID,
    show_all: bool = Query(
        False,
        title='Показывать все столы?',
        description='Показывать все столы в кафе или нет.',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> list[dict]:
    """Получение списка доступных для бронирования столов в кафе.

    Для администраторов и менеджеров - все столы (с возможностью выбора),
    для пользователей - только активные.
    """
    is_privileged = is_admin_or_manager(current_user)
    show_all_effective = show_all if is_privileged else False

    await ensure_cafe_exists_cached(
        db,
        cafe_id,
        cache,
        require_active=not show_all_effective,
    )

    key = key_cafe_tables(cafe_id, show_all=show_all_effective)
    ttl = settings.cache.TTL_CAFE_TABLES

    cached = await cache_get_list(cache, key, TableWithCafeInfo)
    if cached is not None:
        if len(cached) == 0:
            raise NotFoundException('В этом кафе нет столов.')
        return cached

    tables = await table_crud.list_tables(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        show_all=show_all_effective,
    )
    if not tables:
        await cache_set(cache, key, [], ttl)
        raise NotFoundException('В этом кафе нет столов.')

    logger.info(
        'GET /cafes/%s/tables: %d tables (show_all=%s)',
        cafe_id,
        len(tables),
        show_all_effective,
        extra={
            'user_id': str(current_user.id),
            'user_role': getattr(
                current_user.role,
                'value',
                str(current_user.role),
            ),
            'cafe_id': str(cafe_id),
            'show_all': show_all_effective,
            'tables_count': len(tables),
        },
    )

    payload = dump_list(TableWithCafeInfo, tables)
    await cache_set(cache, key, payload, ttl)

    return payload


@router.post(
    '/{cafe_id}/tables',
    response_model=TableWithCafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового стола в кафе',
    responses=CREATE_RESPONSES,
)
async def create_table(
    cafe_id: UUID,
    table_data: TableCreate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> dict:
    """Создает новый стол в кафе.

    Только для администраторов и менеджеров.
    """
    await ensure_cafe_exists_cached(db, cafe_id, cache)
    await ensure_manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
        cache=cache,
    )

    try:
        table = await table_crud.create_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            data=table_data,
            cafe_checked=True,
        )
        if table is None:
            raise ValidationErrorException(
                'Неудалось создать объект стола.',
            )

        logger.info(
            'Стол %s в кафе %s создан пользователем %s',
            table.id,
            cafe_id,
            current_user.id,
            extra={
                'user_id': str(current_user.id),
                'user_role': getattr(
                    current_user.role,
                    'value',
                    str(current_user.role),
                ),
                'cafe_id': str(cafe_id),
                'table_id': str(table.id),
            },
        )

        await invalidate_tables_cache(cache, cafe_id)

        return dump_one(TableWithCafeInfo, table)

    except (ValueError,) as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except (PermissionError,) as e:
        await db.rollback()
        raise ForbiddenException(str(e)) from e

    except (LookupError,) as e:
        await db.rollback()
        raise NotFoundException(str(e)) from e

    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных. Попробуйте позже.',
        ) from e


@router.get(
    '/{cafe_id}/tables/{table_id}',
    response_model=TableWithCafeInfo,
    summary='Получение информации о столе по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def get_table_by_id(
    cafe_id: UUID,
    table_id: UUID,
    show_all: bool = Query(
        False,
        title='Показывать неактивные столы?',
        description=(
            'Только для администраторов и менеджеров. '
            'Если false — только активные.',
        ),
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> dict:
    """Получение информации о столе в кафе по его ID.

    Для администраторов и менеджеров - все столы,
    для пользователей - только активные.
    """
    is_privileged = is_admin_or_manager(current_user)
    show_all_effective = show_all if is_privileged else False

    await ensure_cafe_exists_cached(
        db,
        cafe_id,
        cache,
        require_active=not show_all_effective,
    )

    key = key_cafe_table(cafe_id, table_id, show_all=show_all_effective)
    ttl = settings.cache.TTL_CAFE_TABLE

    cached = await cache_get_one(cache, key, TableWithCafeInfo)
    if cached is not None:
        return cached

    table = await table_crud.get_table(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        table_id=table_id,
        show_all=show_all_effective,
    )
    if not table:
        raise NotFoundException('Стол не найден.')

    payload = dump_one(TableWithCafeInfo, table)
    await cache_set(cache, key, payload, ttl)
    return payload


@router.patch(
    '/{cafe_id}/tables/{table_id}',
    response_model=TableWithCafeInfo,
    summary='Обновление информации о столе по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def update_table(
    cafe_id: UUID,
    table_id: UUID,
    table_data: TableUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> dict:
    """Обновление информации о столе в кафе по его ID.

    Только для администраторов и менеджеров.
    """
    await ensure_cafe_exists_cached(db, cafe_id, cache)
    await ensure_manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
        cache=cache,
    )

    try:
        table = await table_crud.update_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            table_id=table_id,
            data=table_data,
            cafe_checked=True,
        )
        if table is None:
            raise NotFoundException('Стол не найден.')

        await invalidate_tables_cache(cache, cafe_id)

        logger.info(
            'Стол %s в кафе %s изменен пользователем %s',
            table.id,
            cafe_id,
            current_user.id,
            extra={
                'user_id': str(current_user.id),
                'user_role': getattr(
                    current_user.role,
                    'value',
                    str(current_user.role),
                ),
                'cafe_id': str(cafe_id),
                'table_id': str(table.id),
                'updated_fields': sorted(table_data.model_fields_set),
            },
        )

        return dump_one(TableWithCafeInfo, table)

    except (ValueError,) as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except (PermissionError,) as e:
        await db.rollback()
        raise ForbiddenException(str(e)) from e

    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных. Попробуйте позже.',
        ) from e
