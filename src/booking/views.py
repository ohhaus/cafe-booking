from datetime import date
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.crud import BookingCRUD
from src.booking.exceptions import handle_booking_exceptions
from src.booking.models import Booking, BookingStatus
from src.booking.schemas import BookingCreate, BookingInfo, BookingUpdate
from src.booking.services import create_or_update_booking
from src.booking.validators import (
    validate_booking_db_constraints,
    validate_create_booking,
    validate_patch_cafe_change_requires_tables_slots,
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
    responses={
        201: {'description': 'Успешно'},
        400: {'description': 'Ошибка в параметрах запроса'},
        401: {'description': 'Неавторизированный пользователь'},
        422: {'description': 'Ошибка валидации данных'},
    },
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
    """Создаёт новое бронирование.

    Args:
        booking_data (BookingCreate): Данные для создания брони.
        current_user (User): Текущий авторизованный пользователь.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        BookingInfo: Созданная бронь с подробной информацией.

    """
    user_id = current_user.id
    try:
        crud = BookingCRUD(db)
        await validate_create_booking(crud, booking_data, current_user)

        # Создание брони
        pairs = [(ts.table_id, ts.slot_id) for ts in booking_data.tables_slots]
        booking = await create_or_update_booking(
            crud=crud,
            current_user_id=user_id,
            booking=None,
            data=booking_data,
            tables_slots=pairs,
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
    responses={
        200: {'description': 'Успешно'},
        401: {'description': 'Неавторизированный пользователь'},
        422: {'description': 'Ошибка валидации данных'},
    },
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
    responses={
        200: {'description': 'Успешно'},
        401: {'description': 'Неавторизированный пользователь'},
        403: {'description': 'Доступ запрещён'},
        404: {'description': 'Бронирование не найдено'},
        422: {'description': 'Некорректный формат ID'},
    },
)
async def get_booking_by_id(
    booking_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Получить бронирование по ID с учётом прав доступа.

    Args:
        booking_id (UUID): ID бронирования.
        current_user (User): Текущий авторизованный пользователь.
        session (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        BookingInfo: Данные бронирования.

    Raises:
        HTTPException: 404 если бронирование не найдено или недоступно.

    """
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


def _apply_status_is_active(
    booking: Booking,
    data: Dict[str, Any],
) -> None:
    """Обновляет статус и активность брони с учётом бизнес-логики."""
    if 'status' in data and data['status'] is not None:
        new_status: BookingStatus = data['status']
        old_status: BookingStatus = booking.status

        booking.status = new_status

        if new_status == BookingStatus.CANCELED:
            if booking.active:
                booking.active = False
                booking.cancel_booking()
        else:
            if (old_status == BookingStatus.CANCELED) or (not booking.active):
                booking.active = True
                booking.restore_booking()

        return

    if 'is_active' in data and data['is_active'] is not None:
        new_active: bool = bool(data['is_active'])
        old_active: bool = bool(booking.active)

        if old_active is True and new_active is False:
            booking.active = False
            booking.cancel_booking()
            booking.status = BookingStatus.CANCELED
        elif old_active is False and new_active is True:
            booking.active = True
            booking.restore_booking()
            if booking.status == BookingStatus.CANCELED:
                booking.status = BookingStatus.BOOKING


Pair = Tuple[UUID, UUID]


def _active_pairs(booking: Booking) -> list[Pair]:
    """Возвращает список активных пар (table_id, slot_id) для бронирования."""
    return [
        (bts.table_id, bts.slot_id)
        for bts in booking.booking_table_slots
        if bts.active
    ]


@router.patch('/{booking_id}', response_model=BookingInfo)
async def patch_booking(
    booking_id: UUID,
    patch_data: BookingUpdate,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> BookingInfo | None:
    """Частично обновляет бронирование по его ID.

    Поддерживает обновление cafe_id, даты, гостей, статуса, активности и
    связей стол-слот.
    Проверяет бизнес-логику и целостность данных.
    """
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

        booking = await crud.get_booking_by_id(
            booking_id,
            current_user_id=user_id,
            is_staff=is_staff,
        )
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено.',
            )

        validate_patch_cafe_change_requires_tables_slots(
            incoming_data=data,
            current_cafe_id=booking.cafe_id,
        )

        effective_cafe_id: UUID = data.get(
            'cafe_id',
            booking.cafe_id,
        )
        effective_booking_date: date = data.get(
            'booking_date',
            booking.booking_date,
        )
        effective_guest_number: int = data.get(
            'guest_number',
            booking.guest_number,
        )

        current_pairs = _active_pairs(booking)

        incoming_pairs: Optional[list[Pair]] = None
        replace_tables_slots = 'tables_slots' in data
        if replace_tables_slots:
            incoming_pairs = [
                (ts['table_id'], ts['slot_id']) for ts in data['tables_slots']
            ]

        # Итоговые пары (после PATCH)
        effective_pairs: list[Pair] = (
            incoming_pairs if (incoming_pairs is not None) else current_pairs
        )

        date_changed = effective_booking_date != booking.booking_date
        guest_number_changed = 'guest_number' in data

        # занятость проверяем только когда:
        # - меняется дата -> все итоговые пары на новой дате
        # - меняются tables_slots -> только пары на effective_booking_date
        pairs_to_check_taken: list[Pair] = []
        if date_changed:
            pairs_to_check_taken = effective_pairs
        elif replace_tables_slots and incoming_pairs is not None:
            pairs_to_check_taken = list(
                set(incoming_pairs) - set(current_pairs),
            )

        # вместимость проверяем когда:
        # - меняется guest_number
        # - меняются tables_slots (потому что меняются столы)
        need_capacity_check = guest_number_changed or replace_tables_slots

        if pairs_to_check_taken:
            await validate_booking_db_constraints(
                crud,
                cafe_id=effective_cafe_id,
                booking_date=effective_booking_date,
                guest_number=effective_guest_number,
                tables_slots=pairs_to_check_taken,
                current_user=current_user,
                exclude_booking_id=booking.id,
                check_taken=True,
                require_tables_slots=False,
            )

        if need_capacity_check and effective_pairs:
            await validate_booking_db_constraints(
                crud,
                cafe_id=effective_cafe_id,
                booking_date=effective_booking_date,
                guest_number=effective_guest_number,
                tables_slots=effective_pairs,
                current_user=current_user,
                exclude_booking_id=booking.id,
                check_taken=False,
                require_tables_slots=False,
            )

        updated = await create_or_update_booking(
            crud=crud,
            current_user_id=user_id,
            booking=booking,
            data=patch_data,
            tables_slots=(
                incoming_pairs if incoming_pairs is not None else None
            ),
        )

        _apply_status_is_active(updated, data)

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
