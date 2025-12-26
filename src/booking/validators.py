from datetime import date
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from starlette import status

from src.booking.crud import BookingCRUD
from src.booking.schemas import BookingCreate
from src.users.models import User


logger = logging.getLogger('app')

Pair = Tuple[UUID, UUID]


async def validate_booking_db_constraints(
    crud: BookingCRUD,
    *,
    cafe_id: UUID,
    booking_date: date,
    guest_number: int,
    tables_slots: List[Pair],
    current_user: Optional[User] = None,
    exclude_booking_id: Optional[UUID] = None,
    check_taken: bool = True,
    require_tables_slots: bool = True,
) -> None:
    """Единый async-валидатор БД для CREATE и PATCH."""
    cafe = await crud.get_cafe(cafe_id)
    if not cafe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Кафе не найдено',
        )

    tables_slots = tables_slots or []
    if require_tables_slots and not tables_slots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Необходимо указать хотя бы один стол и слот.',
        )

    # В PATCH может прийти пустой список — просто выходим.
    if not tables_slots:
        return

    table_ids = [table for (table, _) in tables_slots]
    slot_ids = [slot for (_, slot) in tables_slots]

    # Столы
    unique_table_ids = set(table_ids)
    tables = await crud.get_tables(list(unique_table_ids), cafe_id)
    if len(tables) != len(unique_table_ids):
        missing = unique_table_ids - {t.id for t in tables}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Столы с ID: {missing} не найдены или не активны.',
        )

    # Слоты
    unique_slot_ids = set(slot_ids)
    slots = await crud.get_slots(list(unique_slot_ids), cafe_id)
    if len(slots) != len(unique_slot_ids):
        missing = unique_slot_ids - {s.id for s in slots}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Слоты с ID: {missing} не найдены или не активны.',
        )

    # Вместимость
    if not require_tables_slots and not await crud.check_capacity(
        list(table_ids),
        guest_number,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Количество гостей {guest_number} превышает '
            f'вместимость столов',
        )

    # Занятость
    if check_taken:
        for table_id, slot_id in tables_slots:
            taken = await crud.is_slot_taken(
                table_id=table_id,
                slot_id=slot_id,
                booking_date=booking_date,
                exclude_booking_id=exclude_booking_id,
            )
            if taken:
                logger.warning(
                    'Стол %s в слоте %s уже забронирован на %s',
                    table_id,
                    slot_id,
                    booking_date,
                    extra={'user_id': str(getattr(current_user, 'id', ''))},
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f'Стол {table_id} в слоте {slot_id} уже '
                        f'забронирован на {booking_date}'
                    ),
                )


async def validate_create_booking(
    crud: BookingCRUD,
    booking_data: BookingCreate,
    current_user: User,
) -> None:
    """Проверки БД для CREATE."""
    pairs: List[Pair] = [
        (ts.table_id, ts.slot_id) for ts in booking_data.tables_slots
    ]
    await validate_booking_db_constraints(
        crud,
        cafe_id=booking_data.cafe_id,
        booking_date=booking_data.booking_date,
        guest_number=booking_data.guest_number,
        tables_slots=pairs,
        current_user=current_user,
        exclude_booking_id=None,
        check_taken=True,
        require_tables_slots=True,
    )


def validate_patch_cafe_change_requires_tables_slots(
    *,
    incoming_data: dict,
    current_cafe_id: UUID,
) -> None:
    """Запрет смены cafe_id без явной передачи tables_slots."""
    cafe_in_payload = 'cafe_id' in incoming_data
    tables_in_payload = 'tables_slots' in incoming_data

    if cafe_in_payload and incoming_data.get('cafe_id') != current_cafe_id:
        if not tables_in_payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    'Изменение cafe_id возможно только при явной передаче '
                    '"tables_slots" (списка столов и слотов) для нового кафе.'
                ),
            )
