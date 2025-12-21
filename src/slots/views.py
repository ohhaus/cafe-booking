import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.service import is_admin_or_manager
from src.database.sessions import get_async_session
from src.slots.crud import SlotService
from src.slots.schemas import (
    TimeSlotCreate,
    TimeSlotUpdate,
    TimeSlotWithCafeInfo,
)
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter(
    tags=['Временные слоты'],
)

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
    responses={
        200: {'description': 'Успешно'},
        401: {'description': 'Неавторизированный пользователь'},
        404: {'description': 'Данные не найдены'},
        422: {'description': 'Ошибка валидации данных'},
    },
)
async def get_time_slots(
    cafe_id: UUID,
    show_all: Optional[bool] = Query(
        None,
        title='Показывать все временные слоты?',
        description='Показывать все временные слоты в кафе или нет.',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> list[TimeSlotWithCafeInfo]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Для администраторов и менеджеров - все столы (с возможностью выбора),
    для пользователей - только активные.
    """
    try:
        crud = SlotService()

        cafe = await SlotService._get_cafe_or_none(db, cafe_id)
        if not cafe:
            logger.warning(
                'Кафе %s не найдено при получении списка слотов',
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

        privileged = is_admin_or_manager(current_user)
        include_all = (
            (True if show_all is None else show_all) if privileged else False
        )

        slots = await crud.list_slots(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            show_all=include_all,
        )

        logger.info(
            'GET /cafe/%s/time_slots: найдено %d '
            '(include_all=%s, show_all=%s)',
            cafe_id,
            len(slots),
            include_all,
            show_all,
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )

        return [TimeSlotWithCafeInfo.model_validate(slot) for slot in slots]

    except asyncio.CancelledError:
        raise

    except HTTPException:
        raise

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при получении списка слотов (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при получении списка слотов (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


@router.post(
    '/{cafe_id}/time_slots',
    response_model=TimeSlotWithCafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового временного слота в кафе',
    responses={
        201: {'description': 'Успешно'},
        400: {'description': 'Ошибка в параметрах запроса'},
        401: {'description': 'Неавторизированный пользователь'},
        403: {'description': 'Доступ запрещен'},
        404: {'description': 'Данные не найдены'},
        422: {'description': 'Ошибка валидации данных'},
    },
)
async def create_time_slot(
    cafe_id: UUID,
    slot_data: TimeSlotCreate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> TimeSlotWithCafeInfo:
    """Создает нового временного слота в кафе.

    Только для администраторов и менеджеров.
    """
    logger.info(
        'Пользователь %s инициализировал создание слота '
        '(cafe=%s, start=%s, end=%s)',
        current_user.id,
        cafe_id,
        slot_data.start_time,
        slot_data.end_time,
        extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
    )

    try:
        crud = SlotService()

        slot = await crud.create_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            data=slot_data,
        )

        # перечитываем, чтобы гарантированно был cafe под response_model
        slot = await crud.get_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            slot_id=slot.id,
        )
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Не удалось получить созданный слот.',
            )

        logger.info(
            'Слот %s успешно создан (cafe=%s)',
            slot.id,
            cafe_id,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot.id),
            },
        )
        return TimeSlotWithCafeInfo.model_validate(slot)

    except asyncio.CancelledError:
        raise

    except ValueError as e:
        await db.rollback()
        logger.warning(
            'Ошибка валидации при создании слота (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except PermissionError as e:
        await db.rollback()
        logger.warning(
            'Доступ запрещен при создании слота (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    except LookupError as e:
        await db.rollback()
        logger.warning(
            'Кафе не найдено при создании слота (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'Ошибка целостности данных при создании слота (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при создании слота (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except HTTPException as e:
        logger.warning(
            'HTTP ошибка при создании слота (cafe=%s): %s',
            cafe_id,
            e.detail,
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при создании слота (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={'user_id': str(current_user.id), 'cafe_id': str(cafe_id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


@router.get(
    '/{cafe_id}/time_slots/{slot_id}',
    response_model=TimeSlotWithCafeInfo,
    summary='Получение информации о временном слоте по ID',
    responses={
        200: {'description': 'Успешно'},
        400: {'description': 'Ошибка в параметрах запроса'},
        401: {'description': 'Неавторизированный пользователь'},
        403: {'description': 'Доступ запрещен'},
        404: {'description': 'Данные не найдены'},
        422: {'description': 'Ошибка валидации данных'},
    },
)
async def get_time_slot_by_id(
    cafe_id: UUID,
    slot_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> TimeSlotWithCafeInfo:
    """Получение информации о временном слоте в кафе по его ID.

    Для администраторов и менеджеров - все столы,
    для пользователей - только активные.
    """
    try:
        crud = SlotService()

        logger.info(
            'Пользователь %s запрашивает слот %s (cafe=%s)',
            current_user.id,
            slot_id,
            cafe_id,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )

        slot = await crud.get_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            slot_id=slot_id,
        )
        if not slot:
            logger.warning(
                'Слот %s не найден (cafe=%s)',
                slot_id,
                cafe_id,
                extra={
                    'user_id': str(current_user.id),
                    'cafe_id': str(cafe_id),
                    'slot_id': str(slot_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Слот не найден.',
            )

        return TimeSlotWithCafeInfo.model_validate(slot)

    except asyncio.CancelledError:
        raise

    except HTTPException:
        raise

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при получении слота (cafe=%s, slot=%s): %s',
            cafe_id,
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при получении слота (cafe=%s, slot=%s): %s',
            cafe_id,
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


@router.patch(
    '/{cafe_id}/time_slots/{slot_id}',
    response_model=TimeSlotWithCafeInfo,
    summary='Обновление информации о временном слоте по ID',
    responses={
        200: {'description': 'Успешно'},
        400: {'description': 'Ошибка в параметрах запроса'},
        401: {'description': 'Неавторизированный пользователь'},
        403: {'description': 'Доступ запрещен'},
        404: {'description': 'Данные не найдены'},
        422: {'description': 'Ошибка валидации данных'},
    },
)
async def update_time_slot(
    cafe_id: UUID,
    slot_id: UUID,
    slot_data: TimeSlotUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> TimeSlotWithCafeInfo:
    """Обновление информации о временом слоте в кафе по его ID.

    Только для администраторов и менеджеров.
    """
    try:
        crud = SlotService()

        logger.info(
            'Пользователь %s обновляет слот %s (cafe=%s, fields=%s)',
            current_user.id,
            slot_id,
            cafe_id,
            sorted(slot_data.model_fields_set),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )

        slot = await crud.update_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            slot_id=slot_id,
            data=slot_data,
        )
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Слот не найден.',
            )

        logger.info(
            'Слот %s успешно обновлён (cafe=%s)',
            slot.id,
            cafe_id,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot.id),
            },
        )

        return TimeSlotWithCafeInfo.model_validate(slot)

    except asyncio.CancelledError:
        raise

    except ValueError as e:
        await db.rollback()
        logger.error(
            'PATCH slot %s ValueError: %s',
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except PermissionError as e:
        await db.rollback()
        logger.warning(
            'PATCH slot %s Forbidden: %s',
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    except HTTPException as e:
        logger.warning(
            'PATCH slot %s HTTPException: %s',
            slot_id,
            e.detail,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )
        raise

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'PATCH slot %s IntegrityError: %s',
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
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
            'PATCH slot %s DatabaseError: %s',
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'PATCH slot %s Unexpected error: %s',
            slot_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'slot_id': str(slot_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e
