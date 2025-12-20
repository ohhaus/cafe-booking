from datetime import date
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking import Booking
from src.booking.constants import BookingStatus
from src.booking.crud import BookingCRUD
from src.booking.schemas import BookingCreate, BookingInfo, BookingUpdate
from src.booking.validators import (
    PatchEffectiveData,
    build_patch_effective_data,
    compute_pairs_diff,
    select_pairs_to_check,
    validate_booking_data,
    validate_patch_cafe_change_requires_tables_slots,
    validate_patch_effective_booking,
    validate_patch_not_empty,
    validate_patch_status_is_active_consistency,
)
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter(
    prefix='/booking',
    tags=['Бронирования'],
)

logger = logging.getLogger('app')


@router.post(
    '/',
    response_model=BookingInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создать бронирование',
    description='Создать новое бронирование для указанного кафе и даты. '
    'Только для авторизованных пользователей.',
    responses={
        200: {'description': 'Успешно'},
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
) -> BookingInfo:
    """Создаёт новое бронирование.

    Args:
        booking_data (BookingCreate): Данные для создания брони.
        current_user (User): Текущий авторизованный пользователь.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        BookingInfo: Созданная бронь с подробной информацией.

    """
    logger.info(
        'Пользователь %s инициировал создание бронирования на дату %s',
        current_user.id,
        booking_data.booking_date,
        extra={'user_id': str(current_user.id)},
    )

    try:
        crud = BookingCRUD(db)
        await validate_booking_data(crud, booking_data, current_user)

        # Создание брони
        booking = await crud.create_booking(
            user_id=current_user.id,
            cafe_id=booking_data.cafe_id,
            guest_number=booking_data.guest_number,
            note=booking_data.note,
            status=booking_data.status,
            booking_date=booking_data.booking_date,
        )

        # Создание связей стол-слот
        for ts in booking_data.tables_slots:
            await crud.create_booking_slot(
                booking_id=booking.id,
                table_id=ts.table_id,
                slot_id=ts.slot_id,
                booking_date=booking_data.booking_date,
            )

        await db.commit()
        logger.info(
            'Бронирование %s успешно создано',
            booking.id,
            extra={'user_id': str(current_user.id)},
        )

        await db.refresh(
            booking,
            attribute_names=['booking_table_slots', 'user', 'cafe'],
        )

        return BookingInfo.model_validate(booking)

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'Ошибка целостности данных при создании брони: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных: возможно, дублирующая бронь или '
            'нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при создании брони: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except HTTPException as e:
        logger.warning(
            'HTTP ошибка при создании брони: %s',
            e.detail,
            extra={'user_id': str(current_user.id)},
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при создании брони: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


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
) -> List[BookingInfo]:
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

        logger.info(
            'Найдено %d бронирований для пользователя %s',
            len(bookings),
            current_user.id,
            extra={'user_id': str(current_user.id)},
        )

        return [BookingInfo.model_validate(b) for b in bookings]

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении бронирований: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении бронирований: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


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
) -> BookingInfo:
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
        logger.info(
            'Пользователь %s запрашивает бронирование %s',
            current_user.id,
            booking_id,
            extra={'user_id': str(current_user.id)},
        )

        crud = BookingCRUD(session)
        booking = await crud.get_booking_by_id(
            booking_id,
            current_user_id=current_user.id,
            is_staff=current_user.is_staff(),
        )

        if not booking:
            logger.warning(
                'Бронирование %s не найдено',
                booking_id,
                extra={'user_id': str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено.',
            )

        return BookingInfo.model_validate(booking)

    except HTTPException:
        raise

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении бронирования: %s',
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении бронирования: %s',
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


def _apply_simple_fields(
    booking: Booking,
    data: Dict[str, Any],
    effective: PatchEffectiveData,
) -> None:
    """Применяет изменения к простым полям бронирования."""
    if 'cafe_id' in data:
        booking.cafe_id = effective.cafe_id
    if 'guest_number' in data:
        booking.guest_number = effective.guest_number
    if 'note' in data:
        booking.note = effective.note
    if 'booking_date' in data:
        booking.booking_date = effective.booking_date


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


async def _apply_tables_slots_patch(
    *,
    crud: BookingCRUD,
    booking: Booking,
    replace_tables_slots: bool,
    incoming_pairs: Set[Tuple[UUID, UUID]],
    new_pairs: Set[Tuple[UUID, UUID]],
    effective_booking_date: date,
    date_changed: bool,
) -> None:
    """Применяет изменения к парам стол-слот с учётом добавления и удаления."""
    if replace_tables_slots:
        for bts in booking.booking_table_slots:
            pair = (bts.table_id, bts.slot_id)

            if pair in incoming_pairs:
                bts.booking_date = effective_booking_date
                if not bts.active:
                    bts.restore()
            else:
                if bts.active:
                    bts.soft_delete()

        for table_id, slot_id in new_pairs:
            await crud.create_booking_slot(
                booking_id=booking.id,
                table_id=table_id,
                slot_id=slot_id,
                booking_date=effective_booking_date,
            )
        return

    if date_changed:
        for bts in booking.booking_table_slots:
            if bts.active:
                bts.booking_date = effective_booking_date


@router.patch(
    '/{booking_id}',
    response_model=BookingInfo,
    status_code=status.HTTP_200_OK,
    summary='Обновление информации о бронировании по его ID',
    description=(
        'Обновление бронирования по ID. '
        'Для администраторов и менеджеров — любые бронирования, '
        'для пользователей — только свои.'
    ),
    responses={
        200: {'description': 'Успешно'},
        400: {'description': 'Ошибка в параметрах запроса'},
        401: {'description': 'Неавторизированный пользователь'},
        403: {'description': 'Доступ запрещён'},
        404: {'description': 'Бронирование не найдено'},
        422: {'description': 'Ошибка валидации данных'},
    },
)
async def patch_booking(
    booking_id: UUID,
    patch_data: BookingUpdate,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Частично обновляет бронирование."""
    try:
        crud = BookingCRUD(db)
        is_staff = current_user.is_staff()

        data = patch_data.model_dump(exclude_unset=True)

        logger.info(
            'PATCH booking %s от пользователя %s: поля=%s',
            booking_id,
            current_user.id,
            sorted(list(data.keys())),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )

        validate_patch_not_empty(data)

        # 1) Проверить существование брони и права доступа
        booking = await crud.get_booking_by_id(
            booking_id,
            current_user_id=current_user.id,
            is_staff=is_staff,
        )
        if not booking:
            logger.warning(
                'PATCH booking %s: не найдено или нет доступа (user=%s)',
                booking_id,
                current_user.id,
                extra={
                    'user_id': str(current_user.id),
                    'booking_id': str(booking_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено.',
            )

        # 2) Валидации данных PATCH запроса
        # 2.1) Согласованность status / is_active
        validate_patch_status_is_active_consistency(incoming_data=data)

        # 2.2) Запрет смены cafe_id без явного tables_slots
        validate_patch_cafe_change_requires_tables_slots(
            incoming_data=data,
            current_cafe_id=booking.cafe_id,
        )

        # 3) Собрать "эффективные" значения
        current_active_pairs = [
            (bts.table_id, bts.slot_id)
            for bts in booking.booking_table_slots
            if bts.active
        ]

        effective = build_patch_effective_data(
            data,
            current_cafe_id=booking.cafe_id,
            current_booking_date=booking.booking_date,
            current_guest_number=booking.guest_number,
            current_note=booking.note,
            current_active_pairs=current_active_pairs,
        )

        # 4) Валидируем "эффективные" данные
        await validate_patch_effective_booking(
            crud,
            cafe_id=effective.cafe_id,
            booking_date=effective.booking_date,
            guest_number=effective.guest_number,
            tables_slots=effective.pairs_list,
        )

        # 5) tables_slots: расчёт разницы
        existing_pairs: Set[Tuple[UUID, UUID]] = set(current_active_pairs)

        incoming_pairs, new_pairs = compute_pairs_diff(
            existing_active_pairs=existing_pairs,
            incoming_pairs_list=effective.pairs_list,
        )

        date_changed = effective.booking_date != booking.booking_date

        pairs_to_check = select_pairs_to_check(
            date_changed=date_changed,
            replace_tables_slots=effective.replace_tables_slots,
            incoming_pairs=incoming_pairs,
            new_pairs=new_pairs,
        )

        for table_id, slot_id in pairs_to_check:
            if await crud.is_slot_taken(
                table_id=table_id,
                slot_id=slot_id,
                booking_date=effective.booking_date,
                exclude_booking_id=booking.id,
            ):
                logger.warning(
                    'PATCH booking %s: конфликт table=%s slot=%s date=%s',
                    booking_id,
                    table_id,
                    slot_id,
                    effective.booking_date,
                    extra={
                        'user_id': str(current_user.id),
                        'booking_id': str(booking_id),
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f'Стол {table_id} в слоте {slot_id} уже забронирован '
                        f'на {effective.booking_date}'
                    ),
                )

        # 6) Применяем простые поля
        _apply_simple_fields(booking, data, effective)

        # 7) Строгая и однозначная обработка status/is_active
        _apply_status_is_active(booking, data)

        # 8) tables_slots применяем
        await _apply_tables_slots_patch(
            crud=crud,
            booking=booking,
            replace_tables_slots=effective.replace_tables_slots,
            incoming_pairs=incoming_pairs,
            new_pairs=new_pairs,
            effective_booking_date=effective.booking_date,
            date_changed=date_changed,
        )

        await db.commit()

        await db.refresh(
            booking,
            attribute_names=['booking_table_slots', 'user', 'cafe'],
        )

        logger.info(
            'PATCH booking %s успешно: cafe=%s date=%s guests=%s '
            'status=%s active=%s replace_tables_slots=%s',
            booking_id,
            str(booking.cafe_id),
            str(booking.booking_date),
            booking.guest_number,
            str(booking.status),
            bool(booking.active),
            effective.replace_tables_slots,
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )

        return BookingInfo.model_validate(booking)

    except HTTPException as e:
        logger.warning(
            'PATCH booking %s HTTPException: %s',
            booking_id,
            e.detail,
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )
        raise

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'PATCH booking %s IntegrityError: %s',
            booking_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных при обновлении бронирования.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'PATCH booking %s DatabaseError: %s',
            booking_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'PATCH booking %s Unexpected error: %s',
            booking_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e
