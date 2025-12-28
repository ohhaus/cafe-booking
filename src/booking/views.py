import logging
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.crud import BookingCRUD
from src.booking.exceptions import handle_booking_exceptions
from src.booking.schemas import BookingCreate, BookingInfo, BookingUpdate
from src.booking.validators import (
    validate_and_create_booking,
    validate_and_update_booking,
)
from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.post(
    '/',
    response_model=BookingInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создать бронирование',
    description='Создать новое бронирование для указанного кафе и даты. '
    'Только для авторизованных пользователей.',
    responses=create_responses(BookingInfo),
)
async def create_booking(
    booking_data: BookingCreate,
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.USER, UserRole.MANAGER, UserRole.ADMIN],
        ),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Создаёт новое бронирование."""
    user_id = current_user.id
    try:
        crud = BookingCRUD(db)
        booking = await validate_and_create_booking(
            crud=crud,
            booking_data=booking_data,
            current_user_id=user_id,
        )

        await db.commit()
        logger.info(
            'Бронирование %s успешно создано',
            booking.id,
            extra={'user_id': str(user_id)},
        )

        await db.refresh(
            booking,
            attribute_names=['booking_table_slots', 'user', 'cafe'],
        )

        return BookingInfo.model_validate(booking)

    except HTTPException as e:
        raise e

    except Exception as e:
        await db.rollback()
        handle_booking_exceptions(
            e,
            user_id,
            'создании',
        )


@router.get(
    '/',
    response_model=List[BookingInfo],
    summary='Получение списка бронирований',
    description=(
        'Получение списка бронирований. '
        'Для администраторов и менеджеров - все бронирования '
        '(с возможностью выбора), '
        'для пользователей - только свои (параметры игнорируются, '
        'кроме ID кафе).'
    ),
    responses=list_responses(),
)
async def get_all_bookings(
    show_all: bool = Query(
        False,
        title='Показывать все бронирования?',
        description='Показывать все бронирования или нет. По умолчанию '
        'показывает только активные.',
    ),
    cafe_id: Optional[UUID] = Query(
        None,
        title='Cafe Id',
        description='ID кафе, в котором показывать бронирования. Если не '
        'задано - показывает бронирования во всех кафе.',
    ),
    user_id: Optional[UUID] = Query(
        None,
        title='User Id',
        description='ID пользователя, бронирования которого показывать. Если '
        'не задано - показывает бронирования всех пользователей. '
        '(только для staff)',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> list[BookingInfo] | None:
    """Обработчик GET /booking для получения списка бронирований."""
    try:
        crud = BookingCRUD(session)
        is_staff = current_user.is_staff()

        bookings = await crud.get_bookings(
            current_user_id=current_user.id,
            is_staff=is_staff,
            show_all=(show_all if is_staff else False),
            cafe_id=cafe_id,
            user_id=(user_id if is_staff else None),
        )

        return [BookingInfo.model_validate(b) for b in bookings]

    except HTTPException:
        raise

    except Exception as e:
        handle_booking_exceptions(
            e,
            current_user.id,
            'получении списка бронирований',
        )


@router.get(
    '/{booking_id}',
    response_model=BookingInfo,
    summary='Получение информации о бронировании по ID',
    description='Получение полной информации о бронировании по его уникальному'
    ' идентификатору. Пользователь может просматривать только свои'
    ' бронирования, менеджеры и администраторы — любые.',
    responses=retrieve_responses(),
)
async def get_booking_by_id(
    booking_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Получает бронирование по ID с учётом прав доступа."""
    try:
        crud = BookingCRUD(session)
        booking = await crud.get_booking_by_id(
            booking_id,
            current_user_id=current_user.id,
            is_staff=current_user.is_staff(),
        )

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено.',
            )

        return BookingInfo.model_validate(booking)

    except HTTPException:
        raise

    except Exception as e:
        handle_booking_exceptions(
            e,
            current_user.id,
            'получения бронирования по ID',
        )


Pair = Tuple[UUID, UUID]


@router.patch(
    '/{booking_id}',
    response_model=BookingInfo,
    summary='Частичное обновление бронирования',
    description='Частичное обновление бронирования по его ID. ',
    responses=retrieve_responses(),
)
async def patch_booking(
    booking_id: UUID,
    patch_data: BookingUpdate,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Частично обновляет бронирование по его ID."""
    user_id = current_user.id
    try:
        crud = BookingCRUD(db)
        is_staff = current_user.is_staff()

        data = patch_data.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Пустой запрос: нет полей для обновления.',
            )

        updated = await validate_and_update_booking(
            crud=crud,
            booking_id=booking_id,
            incoming_data=data,
            current_user_id=user_id,
            patch_data=patch_data,
            is_staff=is_staff,
        )

        await db.commit()
        await db.refresh(
            updated,
            attribute_names=['booking_table_slots', 'user', 'cafe'],
        )
        return BookingInfo.model_validate(updated)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        handle_booking_exceptions(e, user_id, 'обновлении')
