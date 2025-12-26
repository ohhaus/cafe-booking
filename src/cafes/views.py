import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.crud import CafeService
from src.cafes.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.cafes.schemas import CafeCreate, CafeInfo, CafeUpdate
from src.cafes.service import is_admin_or_manager
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
    responses=GET_RESPONSES,
)
async def create_cafe(
    cafe_data: CafeCreate,
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.MANAGER, UserRole.ADMIN],
        ),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Создает новое кафе. Только для администраторов и менеджеров."""
    logger.info(
        'Пользователь %s инициализировал создание кафе %s',
        current_user.id,
        cafe_data.name,
        extra={'user_id': str(current_user.id)},
    )

    try:
        crud = CafeService()

        cafe = await crud.create_cafe(db, cafe_data)

        logger.info(
            'Кафе %s (%s) успешно создано',
            cafe.id,
            cafe.name,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe.id),
            },
        )
        return CafeInfo.model_validate(cafe)

    except asyncio.CancelledError:
        raise

    except ValueError as e:
        await db.rollback()
        logger.warning(
            'Ошибка валидации при создании кафе: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'Ошибка целостности данных при создании кафе: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных: возможно, дублирующая пара "имя и адрес"'
            'или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при создании кафе: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except HTTPException as e:
        logger.warning(
            'HTTP ошибка при создании кафе: %s',
            e.detail,
            extra={'user_id': str(current_user.id)},
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при создании кафе: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


@router.get(
    '',
    response_model=list[CafeInfo],
    summary=('Получение списка кафе.'),
    description=(
        'Получение списка кафе. Для администраторов и менеджеров - все кафе'
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=CREATE_RESPONSES,
)
async def get_all_cafes(
    show_all: Optional[bool] = Query(
        None,
        title='Показывать все кафе?',
        description=(
            'Показывать все кафе или нет. По умолчанию показывает все кафе'
        ),
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> list[CafeInfo]:
    """Получение списка кафе.

    Для администраторов и менеджеров - все кафе (с возможностью выбора),
    для пользователей - только активные.
    """
    try:
        crud = CafeService()
        privileged = is_admin_or_manager(current_user)
        include_inactive = (
            (True if show_all is None else show_all) if privileged else False
        )

        cafes = await crud.get_list_cafe(
            db,
            include_inactive=include_inactive,
            skip=skip,
            limit=limit,
        )
        logger.info(
            'GET /cafes: найдено %d (include_inactive=%s, '
            'show_all=%s, skip=%d, limit=%d)',
            len(cafes),
            include_inactive,
            show_all,
            skip,
            limit,
            extra={'user_id': str(current_user.id)},
        )

        return [CafeInfo.model_validate(cafe) for cafe in cafes]

    except asyncio.CancelledError:
        raise

    except HTTPException:
        raise

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении списка кафе: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении списка кафе: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


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
) -> CafeInfo:
    """Получение информации о кафе по его ID.

    Для администраторов и менеджеров - все кафе,
    для пользователей - только активные.
    """
    try:
        crud = CafeService()
        include_inactive = is_admin_or_manager(current_user)
        logger.info(
            'Пользователь %s запрашивает кафе %s (include_inactive=%s)',
            current_user.id,
            cafe_id,
            include_inactive,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )

        cafe = await crud.get_cafe_by_id(
            db,
            cafe_id=cafe_id,
            include_inactive=include_inactive,
        )
        if not cafe:
            logger.warning(
                'Кафе %s не найдено',
                cafe_id,
                extra={
                    'user_id': str(current_user.id),
                    'cafe_id': str(cafe_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Кафе не найдено.',
            )
        return CafeInfo.model_validate(cafe)

    except asyncio.CancelledError:
        raise

    except HTTPException:
        raise

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении кафе: %s',
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении кафе: %s',
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


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
) -> CafeInfo:
    """Обновление информации о кафе по его ID.

    Только для администраторов и менеджеров.
    """
    try:
        crud = CafeService()

        logger.info(
            'Пользователь %s обновляет кафе %s (fields=%s)',
            current_user.id,
            cafe_id,
            sorted(cafe_data.model_fields_set),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )

        cafe = await crud.get_cafe_by_id(
            db,
            cafe_id=cafe_id,
            include_inactive=True,
        )
        if cafe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Кафе не найдено',
            )

        cafe = await crud.update_cafe(
            db,
            cafe,
            cafe_data,
        )
        logger.info(
            'Кафе %s успешно обновлено',
            cafe.id,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe.id),
            },
        )
        return CafeInfo.model_validate(cafe)

    except asyncio.CancelledError:
        raise

    except ValueError as e:
        await db.rollback()
        logger.error(
            'PATCH cafe %s ValueError: %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except HTTPException as e:
        logger.warning(
            'PATCH cafe %s HTTPException: %s',
            cafe_id,
            e.detail,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'PATCH cafe %s IntegrityError: %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'PATCH cafe %s DatabaseError: %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'PATCH cafe %s Unexpected error: %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e
