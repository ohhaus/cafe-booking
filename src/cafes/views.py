import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.client import RedisCache, get_cache
from src.cache.keys import key_cafe, key_cafes_list
from src.cafes.cafes_help_caches import (
    cache_get_list,
    cache_get_one,
    cache_set,
    invalidate_cafes_cache,
)
from src.cafes.crud import cafe_crud
from src.cafes.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.cafes.schemas import CafeCreate, CafeInfo, CafeUpdate
from src.cafes.service import ensure_manager_can_cud_cafe, is_admin_or_manager
from src.common.exceptions import (
    NotFoundException,
    ValidationErrorException,
)
from src.config import settings
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.post(
    '',
    response_model=CafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового кафе.',
    responses=CREATE_RESPONSES,
)
async def create_cafe(
    cafe_data: CafeCreate,
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.ADMIN],
        ),
    ),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> CafeInfo:
    """Создает новое кафе. Только для администраторов."""
    try:
        cafe = await cafe_crud.create_cafe(db, cafe_data)
        if cafe is None:
            raise ValidationErrorException('Не удалось создать кафе.')

        await invalidate_cafes_cache(cache, cafe_id=cafe.id)

        logger.info(
            'Кафе %s (%s) успешно создано',
            cafe.id,
            cafe.name,
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe.id)},
        )
        return CafeInfo.model_validate(cafe).model_dump(
            mode='json',
            by_alias=True,
        )

    except ValueError as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e
    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных при создании кафе',
        ) from e
    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных',
        ) from e


@router.get(
    '',
    response_model=list[CafeInfo],
    summary=('Получение списка кафе.'),
    description=(
        'Получение списка кафе. Для администраторов и менеджеров - все кафе'
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,
)
async def get_all_cafes(
    show_all: bool = Query(
        False,
        title='Показывать все кафе?',
        description=(
            'Показывать все кафе или нет. По умолчанию показывает все кафе'
        ),
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> list[CafeInfo]:
    """Получение списка кафе.

    Для администраторов и менеджеров - все кафе (с возможностью выбора),
    для пользователей - только активные.
    """
    is_privileged = is_admin_or_manager(current_user)
    show_all_effective = show_all if is_privileged else False

    key = key_cafes_list(show_all=show_all_effective)
    ttl = settings.cache.TTL_CAFES_LIST

    cached = await cache_get_list(cache, key, CafeInfo)
    if cached is not None:
        return cached

    cafes = await cafe_crud.get_list_cafe(
        db,
        show_all_effective=show_all_effective,
    )

    payload = [
        CafeInfo.model_validate(cafe).model_dump(
            mode='json',
            by_alias=True,
        )
        for cafe in cafes
    ]
    await cache_set(cache, key, payload, ttl)

    logger.info(
        'GET /cafes: найдено %d (show_all_effective=%s, show_all=%s)',
        len(cafes),
        show_all_effective,
        show_all,
        extra={'user_id': str(current_user.id)},
    )

    return payload


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Получение информации о кафе по его ID',
    responses=GET_BY_ID_RESPONSES,
)
async def get_cafe_by_id(
    cafe_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> CafeInfo:
    """Получение информации о кафе по его ID.

    Для администраторов и менеджеров - все кафе,
    для пользователей - только активные.
    """
    show_all_effective = is_admin_or_manager(current_user)

    key = key_cafe(cafe_id, show_all=show_all_effective)
    ttl = settings.cache.TTL_CAFE_BY_ID

    cached = await cache_get_one(cache, key, CafeInfo)
    if cached is not None:
        return cached

    cafe = await cafe_crud.get_cafe_by_id(
        db,
        cafe_id=cafe_id,
        show_all_effective=show_all_effective,
    )
    if not cafe:
        raise NotFoundException('Кафе не найдено')

    payload = CafeInfo.model_validate(cafe).model_dump(
        mode='json',
        by_alias=True,
    )
    await cache_set(cache, key, payload, ttl)
    return payload


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Обновление информации о кафе по его ID',
    responses=GET_BY_ID_RESPONSES,
)
async def update_cafe(
    cafe_id: UUID,
    cafe_data: CafeUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> CafeInfo:
    """Обновление информации о кафе по его ID.

    Только для администраторов и менеджеров.
    """
    cafe = await cafe_crud.get_cafe_by_id(
        db,
        cafe_id=cafe_id,
        show_all_effective=True,
    )
    if cafe is None:
        raise NotFoundException('Кафе не найдено')

    await ensure_manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
        cache=cache,
    )

    try:
        updated = await cafe_crud.update_cafe(db, cafe, cafe_data)
        if updated is None:
            raise ValidationErrorException('Не удалось обновить кафе.')

        await invalidate_cafes_cache(cache, cafe_id=cafe_id)

        logger.info(
            'Кафе %s обновлено пользователем %s',
            cafe_id,
            current_user.id,
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )

        return CafeInfo.model_validate(updated).model_dump(
            mode='json',
            by_alias=True,
        )

    except ValueError as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных при обновлении кафе',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных при обновлении кафе',
        ) from e
