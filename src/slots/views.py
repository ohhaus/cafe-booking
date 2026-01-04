import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.client import RedisCache, get_cache
from src.cache.keys import (
    key_cafe_slot,
    key_cafe_slots,
)
from src.cafes.cafe_scoped import (
    ensure_cafe_exists_cached,
)
from src.cafes.cafes_help_caches import (
    cache_get_list,
    cache_get_one,
    cache_set,
    invalidate_slots_cache,
)
from src.cafes.service import ensure_manager_can_cud_cafe, is_admin_or_manager
from src.common.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationErrorException,
)
from src.config import settings
from src.database.sessions import get_async_session
from src.slots.crud import slot_crud
from src.slots.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.slots.schemas import (
    TimeSlotCreate,
    TimeSlotUpdate,
    TimeSlotWithCafeInfo,
)
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.get(
    '/{cafe_id}/time_slots',
    response_model=list[TimeSlotWithCafeInfo],
    summary='Получение списка временных слотов в кафе',
    description=(
        'Получение списка доступных для бронирования временных слотов в кафе. '
        'Для администраторов и менеджеров - все слоты '
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,
)
async def get_time_slots(
    cafe_id: UUID,
    show_all: bool = Query(
        False,
        title='Показывать все временные слоты?',
        description='Показывать все временные слоты в кафе или нет.',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> list[TimeSlotWithCafeInfo]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Для администраторов и менеджеров - все слоты (с возможностью выбора),
    для пользователей - только активные.
    """
    is_privileged = is_admin_or_manager(current_user)
    show_all_effective = show_all if is_privileged else False

    key = key_cafe_slots(cafe_id, show_all=show_all_effective)
    ttl = settings.cache.TTL_CAFE_SLOTS

    cached = await cache_get_list(cache, key, TimeSlotWithCafeInfo)
    if cached is not None:
        if not show_all_effective:
            meta = await ensure_cafe_exists_cached(db, cafe_id, cache)
            if meta.get('active') is False:
                await cache.delete(key)
                await invalidate_slots_cache(cache, cafe_id)
                logger.info(
                    'Cafe inactive, dropping slots cache (cafe_id=%s, key=%s)',
                    cafe_id,
                    key,
                    extra={
                        'user_id': str(current_user.id),
                        'user_role': getattr(
                            current_user.role,
                            'value',
                            str(current_user.role),
                        ),
                        'cafe_id': str(cafe_id),
                        'show_all': show_all_effective,
                        'cache_key': key,
                        'reason': 'cafe_inactive',
                    },
                )
                raise NotFoundException('Кафе не найдено.')
        return cached

    meta = await ensure_cafe_exists_cached(db, cafe_id, cache)

    if not show_all_effective and meta.get('active') is False:
        raise NotFoundException('Кафе не найдено.')

    slots = await slot_crud.list_slots(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        show_all=show_all_effective,
    )

    logger.info(
        'GET /cafes/%s/time_slots: %d slots (show_all=%s)',
        cafe_id,
        len(slots),
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
            'slots_count': len(slots),
        },
    )

    payload = [
        TimeSlotWithCafeInfo.model_validate(slot).model_dump(
            mode='json',
            by_alias=True,
        )
        for slot in slots
    ]
    await cache_set(cache, key, payload, ttl)

    return payload


@router.post(
    '/{cafe_id}/time_slots',
    response_model=TimeSlotWithCafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового временного слота в кафе',
    responses=CREATE_RESPONSES,
)
async def create_time_slot(
    cafe_id: UUID,
    slot_data: TimeSlotCreate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> TimeSlotWithCafeInfo:
    """Создает нового временного слота в кафе.

    Только для администраторов и менеджеров.
    """
    await ensure_cafe_exists_cached(
        db,
        cafe_id,
        cache,
    )
    await ensure_manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
        cache=cache,
    )

    try:
        slot = await slot_crud.create_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            data=slot_data,
            cafe_checked=True,
        )
        if slot is None:
            raise ValidationErrorException(
                'Неудалось создать объект временного слота.',
            )

        logger.info(
            'Слот %s в кафе %s создан пользователем %s',
            slot.id,
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
                'slot_id': str(slot.id),
            },
        )
        await invalidate_slots_cache(cache, cafe_id)

        return TimeSlotWithCafeInfo.model_validate(slot).model_dump(
            mode='json',
            by_alias=True,
        )

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
    '/{cafe_id}/time_slots/{slot_id}',
    response_model=TimeSlotWithCafeInfo,
    summary='Получение информации о временном слоте по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def get_time_slot_by_id(
    cafe_id: UUID,
    slot_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> TimeSlotWithCafeInfo:
    """Получение информации о временном слоте в кафе по его ID.

    Для администраторов и менеджеров - видят активные и не активные слоты,
    для пользователей - только активные.
    """
    show_all_effective = is_admin_or_manager(current_user)

    key = key_cafe_slot(cafe_id, slot_id, show_all=show_all_effective)
    ttl = settings.cache.TTL_CAFE_SLOT

    cached = await cache_get_one(cache, key, TimeSlotWithCafeInfo)
    if cached is not None:
        if not show_all_effective:
            meta = await ensure_cafe_exists_cached(db, cafe_id, cache)
            if meta.get('active') is False:
                await invalidate_slots_cache(cache, cafe_id)
                raise NotFoundException('Кафе не найдено.')
        return cached

    slot = await slot_crud.get_slot(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        slot_id=slot_id,
    )
    if not slot:
        raise NotFoundException('Слот не найден.')

    payload = TimeSlotWithCafeInfo.model_validate(slot).model_dump(
        mode='json',
        by_alias=True,
    )
    await cache_set(cache, key, payload, ttl)
    return payload


@router.patch(
    '/{cafe_id}/time_slots/{slot_id}',
    response_model=TimeSlotWithCafeInfo,
    summary='Обновление информации о временном слоте по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def update_time_slot(
    cafe_id: UUID,
    slot_id: UUID,
    slot_data: TimeSlotUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> TimeSlotWithCafeInfo:
    """Обновление информации о временом слоте в кафе по его ID.

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
        slot = await slot_crud.update_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            slot_id=slot_id,
            data=slot_data,
            cafe_checked=True,
        )
        if slot is None:
            raise NotFoundException('Слот не найден.')

        await invalidate_slots_cache(cache, cafe_id)

        logger.info(
            'Слот %s в кафе %s изменен пользователем %s',
            slot.id,
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
                'slot_id': str(slot.id),
                'updated_fields': sorted(slot_data.model_fields_set),
            },
        )

        return TimeSlotWithCafeInfo.model_validate(slot).model_dump(
            mode='json',
            by_alias=True,
        )

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
