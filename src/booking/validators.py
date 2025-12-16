from datetime import date, timedelta
import logging
from typing import List
from uuid import UUID

from fastapi import HTTPException
from starlette import status

from src.booking.constants import BookingStatus, MAX_BOOKING_DATE
from src.booking.crud import BookingCRUD
from src.booking.schemas import BookingCreate
from src.users.models import User


logger = logging.getLogger('app')


async def validate_booking_data(
    crud: BookingCRUD,
    booking_data: BookingCreate,
    current_user: User,
) -> None:
    """Выполняет все проверки данных перед созданием брони."""
    # Проверка статуса: только BOOKING или ACTIVE разрешены для создания
    if booking_data.status not in (
        BookingStatus.BOOKING,
        BookingStatus.ACTIVE,
    ):
        logger.warning(
            'Недопустимый статус при создании брони: %s',
            booking_data.status,
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='При создании бронирования допустимы только статусы: '
            'CREATED (0) или ACTIVE (2).',
        )

    # Проверка даты
    today = date.today()
    max_date = today + timedelta(days=MAX_BOOKING_DATE)

    if not (today <= booking_data.booking_date <= max_date):
        logger.warning(
            'Недопустимая дата бронирования: %s',
            booking_data.booking_date,
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Дата бронирования должна быть в диапазоне от сегодня '
            f'до {MAX_BOOKING_DATE} дней вперёд.',
        )

    # Проверка кафе
    cafe = await crud.get_cafe(booking_data.cafe_id)
    if not cafe:
        logger.warning(
            'Кафе с ID %s не найдено',
            booking_data.cafe_id,
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Кафе не найдено',
        )

    table_ids: List[UUID] = [ts.table_id for ts in booking_data.tables_slots]
    slot_ids: List[UUID] = [ts.slot_id for ts in booking_data.tables_slots]

    # Проверка столов
    tables = await crud.get_tables(table_ids, booking_data.cafe_id)
    if len(tables) != len(table_ids):
        missing = set(table_ids) - {t.id for t in tables}
        logger.warning(
            'Столы не найдены или не активны: %s',
            missing,
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Один или более столов не найдено или не активны.',
        )

    # Проверка слотов
    slots = await crud.get_slots(slot_ids, booking_data.cafe_id)
    if len(slots) != len(slot_ids):
        missing = set(slot_ids) - {s.id for s in slots}
        logger.warning(
            'Слоты не найдены или не активны: %s',
            missing,
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Один или более слотов не найдено или не активны.',
        )

    # Проверка вместимости
    if not await crud.check_capacity(table_ids, booking_data.guest_number):
        logger.warning(
            'Превышена вместимость: гостей=%d',
            booking_data.guest_number,
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Количество гостей превышает вместимость столов',
        )

    # Проверка занятости
    for ts in booking_data.tables_slots:
        if await crud.is_slot_taken(
            table_id=ts.table_id,
            slot_id=ts.slot_id,
            booking_date=booking_data.booking_date,
        ):
            logger.warning(
                'Стол %s в слоте %s уже забронирован на %s',
                ts.table_id,
                ts.slot_id,
                booking_data.booking_date,
                extra={'user_id': current_user.id},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Стол {ts.table_id} в слоте {ts.slot_id} уже '
                f'забронирован на {booking_data.booking_date}',
            )
