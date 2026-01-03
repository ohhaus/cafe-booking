import logging
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.schemas import BookingCreate, BookingInfo, BookingUpdate
from src.booking.services import (
    BookingValidationService,
    get_booking_by_id_service,
    get_bookings_service,
)
from src.cache.client import cache
from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User


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
        require_roles(),
    ),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Создаёт новое бронирование."""
    validation_service = BookingValidationService(
        session=session,
        client_cache=cache,
    )
    booking = await validation_service.validate_and_create_booking(
        data=booking_data,
        current_user_id=current_user.id,
    )

    logger.info(
        'Бронирование %s успешно создано',
        booking.id,
        extra={'user_id': str(current_user.id)},
    )

    await session.refresh(
        booking,
        attribute_names=['booking_table_slots', 'user', 'cafe'],
    )

    return BookingInfo.model_validate(booking)


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
    current_user: User = Depends(require_roles()),
    session: AsyncSession = Depends(get_async_session),
) -> list[BookingInfo] | None:
    """Обработчик GET /booking для получения списка бронирований."""
    bookings = await get_bookings_service(
        session=session,
        current_user=current_user,
        show_all=show_all,
        cafe_id=cafe_id,
        user_id=user_id,
    )

    return [BookingInfo.model_validate(b) for b in bookings]


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
    current_user: User = Depends(require_roles()),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Получает бронирование по ID с учётом прав доступа."""
    booking = await get_booking_by_id_service(
        session=session,
        booking_id=booking_id,
        current_user=current_user,
        is_staff=current_user.is_staff(),
    )

    return BookingInfo.model_validate(booking)


Pair = Tuple[UUID, UUID]


@router.patch(
    '/{booking_id}',
    response_model=BookingInfo,
    summary='Частичное обновление бронирования',
    description='Частичное обновление бронирования по его ID. '
    'Для администраторов и менеджеров - все бронирования, '
    'для пользователей - только свои.',
    responses=retrieve_responses(),
)
async def patch_booking(
    booking_id: UUID,
    patch_data: BookingUpdate,
    current_user: User = Depends(require_roles()),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Частично обновляет бронирование по его ID."""
    validation_service = BookingValidationService(
        session=session,
        client_cache=cache,
    )
    updated_booking = await validation_service.validate_and_update_booking(
        booking_id=booking_id,
        current_user=current_user,
        patch_data=patch_data,
    )

    await session.refresh(
        updated_booking,
        attribute_names=['booking_table_slots', 'user', 'cafe'],
    )

    return BookingInfo.model_validate(updated_booking)
