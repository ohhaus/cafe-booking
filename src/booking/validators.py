from datetime import date
import logging
from typing import List, Optional, Set, Tuple
from uuid import UUID

from fastapi import HTTPException
from starlette import status

from src.booking.constants import BookingStatus
from src.booking.crud import BookingCRUD
from src.booking.models import Booking
from src.booking.schemas import BookingCreate, BookingUpdate
from src.booking.services import create_or_update_booking


logger = logging.getLogger('app')

Pair = Tuple[UUID, UUID]


async def validate_cafe_exists(crud: BookingCRUD, cafe_id: UUID) -> None:
    """Проверяет, что кафе существует и активно."""
    cafe = await crud.get_cafe(cafe_id)
    if not cafe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Кафе не найдено',
        )


async def validate_tables_slots_exist_and_belong_to_cafe(
    crud: BookingCRUD,
    *,
    cafe_id: UUID,
    tables_slots: List[Pair],
    require_non_empty: bool,
) -> List[UUID]:
    """Валидирует, что столы/слоты существуют, активны и принадлежат кафе.

    Возвращает table_ids (с повторами, как в исходных парах).
    """
    await validate_cafe_exists(crud, cafe_id)

    pairs = list(tables_slots or [])
    if require_non_empty and not pairs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Необходимо указать хотя бы один стол и слот.',
        )

    # Нечего проверять дальше
    if not pairs:
        return []

    table_ids = [t for (t, _) in pairs]
    slot_ids = [s for (_, s) in pairs]

    unique_table_ids: Set[UUID] = set(table_ids)
    tables = await crud.get_tables(list(unique_table_ids), cafe_id)
    if len(tables) != len(unique_table_ids):
        missing = unique_table_ids - {t.id for t in tables}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Столы с ID: {missing} не найдены или не активны.',
        )

    unique_slot_ids: Set[UUID] = set(slot_ids)
    slots = await crud.get_slots(list(unique_slot_ids), cafe_id)
    if len(slots) != len(unique_slot_ids):
        missing = unique_slot_ids - {s.id for s in slots}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Слоты с ID: {missing} не найдены или не активны.',
        )

    return table_ids


async def validate_capacity(
    crud: BookingCRUD,
    *,
    table_ids: List[UUID],
    guest_number: int,
) -> None:
    """Проверяет, что суммарная вместимость столов >= количества гостей."""
    # если столов нет — либо это "не о чем говорить", либо бизнес-ошибка
    # (обычно сюда не зовём с пустым списком)
    if not table_ids:
        return

    ok = await crud.check_capacity(list(table_ids), guest_number)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f'Количество гостей {guest_number} превышает '
                f'вместимость столов'
            ),
        )


async def validate_table_slot_is_not_booked(
    crud: BookingCRUD,
    *,
    tables_slots: List[Pair],
    booking_date: date,
    exclude_booking_id: Optional[UUID] = None,
) -> None:
    """Проверяет, что указанные пары стол-слот не заняты на дату."""
    pairs = list(tables_slots or [])
    if not pairs:
        return

    for table_id, slot_id in pairs:
        taken = await crud.is_table_slot_taken(
            table_id=table_id,
            slot_id=slot_id,
            booking_date=booking_date,
            exclude_booking_id=exclude_booking_id,
        )
        if taken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f'Стол {table_id} в слоте {slot_id} уже '
                    f'забронирован на {booking_date}'
                ),
            )


async def validate_and_create_booking(
    crud: BookingCRUD,
    booking_data: BookingCreate,
    current_user_id: UUID,
) -> Booking:
    """Полная валидация и создание бронирования.

    Проверяет бизнес-логику, конфликты и вместимость, затем создает бронь.
    Возвращает созданный объект Booking.
    """
    # 1) Проверяем кафе
    await validate_cafe_exists(crud, booking_data.cafe_id)

    # 2) Проверяем столы и слоты
    table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
        crud,
        cafe_id=booking_data.cafe_id,
        tables_slots=[
            (ts.table_id, ts.slot_id) for ts in booking_data.tables_slots
        ],
        require_non_empty=True,
    )

    # 3) Проверяем вместимость
    await validate_capacity(
        crud,
        table_ids=table_ids,
        guest_number=booking_data.guest_number,
    )

    # 4) Проверяем занятость
    await validate_table_slot_is_not_booked(
        crud,
        tables_slots=[
            (ts.table_id, ts.slot_id) for ts in booking_data.tables_slots
        ],
        booking_date=booking_data.booking_date,
        exclude_booking_id=None,
    )

    # 5) Создание брони
    pairs = [(ts.table_id, ts.slot_id) for ts in booking_data.tables_slots]
    return await create_or_update_booking(
        crud=crud,
        current_user_id=current_user_id,
        booking=None,
        data=booking_data,
        tables_slots=pairs,
    )


def validate_patch_cafe_change_requires_tables_slots(
    *,
    incoming_data: dict,
    current_cafe_id: UUID,
) -> None:
    """Запрещает изменение cafe_id без одновременного указания tables_slots."""
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


async def validate_and_update_booking(
    crud: BookingCRUD,
    booking_id: UUID,
    incoming_data: dict,
    current_user_id: UUID,
    patch_data: BookingUpdate,
    is_staff: bool,
) -> Booking:
    """Полная валидация и обновление бронирования.

    Проверяет бизнес-логику, конфликты и вместимость, затем обновляет бронь.
    Возвращает обновлённый объект Booking.
    """
    # 1) Получение брони с проверкой доступа
    current_booking = await crud.get_booking_by_id(
        booking_id,
        current_user_id=current_user_id,
        is_staff=is_staff,
    )
    if not current_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Бронирование не найдено.',
        )

    # 2) Обработка отмены брони — завершаем обработку
    if (
        'status' in incoming_data
        and incoming_data['status'] == BookingStatus.CANCELED
    ):
        current_booking.cancel_booking()
        if 'note' in incoming_data:
            current_booking.note = incoming_data['note']
        return current_booking

    # 3) запрет смены cafe без tables_slots
    validate_patch_cafe_change_requires_tables_slots(
        incoming_data=incoming_data,
        current_cafe_id=current_booking.cafe_id,
    )

    # 4) effective значения
    effective_cafe_id: UUID = incoming_data.get(
        'cafe_id',
        current_booking.cafe_id,
    )
    effective_date: date = incoming_data.get(
        'booking_date',
        current_booking.booking_date,
    )
    effective_guest_number: int = incoming_data.get(
        'guest_number',
        current_booking.guest_number,
    )

    replace_tables_slots = 'tables_slots' in incoming_data
    date_changed = effective_date != current_booking.booking_date
    guest_number_changed = 'guest_number' in incoming_data

    # 5) current_pairs (активные связи из брони)
    current_pairs: List[Pair] = [
        (bts.table_id, bts.slot_id)
        for bts in current_booking.booking_table_slots
        if getattr(bts, 'is_active', True)  # TODO: нужно ли?
    ]

    # 6) incoming_pairs (если пришли)
    incoming_pairs: Optional[List[Pair]] = None
    if replace_tables_slots:
        incoming_pairs = [
            (ts['table_id'], ts['slot_id'])
            # if isinstance(ts, dict)  # TODO: нужно ли?
            # else (ts.table_id, ts.slot_id)
            for ts in incoming_data['tables_slots']
        ]

    # 7) effective_pairs после PATCH
    effective_pairs: List[Pair] = (
        incoming_pairs if (incoming_pairs is not None) else current_pairs
    )

    # 8) какие пары проверять на "занято"
    pairs_to_check_taken: List[Pair] = []
    if date_changed:
        # дата меняется -> проверяем все итоговые пары на новой дате
        pairs_to_check_taken = effective_pairs
    elif replace_tables_slots and incoming_pairs is not None:
        # tables_slots меняются, дата прежняя -> проверяем добавленные пары
        pairs_to_check_taken = list(set(incoming_pairs) - set(current_pairs))

    # 9) проверка доступность столов/слотов, только если есть что проверять
    if pairs_to_check_taken:
        _ = await validate_tables_slots_exist_and_belong_to_cafe(
            crud,
            cafe_id=effective_cafe_id,
            tables_slots=pairs_to_check_taken,
            require_non_empty=True,
        )
        await validate_table_slot_is_not_booked(
            crud,
            tables_slots=pairs_to_check_taken,
            booking_date=effective_date,
            exclude_booking_id=current_booking.id,
        )

    # 10) вместимость проверяем когда меняются гости или меняются столы
    need_capacity_check = guest_number_changed or replace_tables_slots

    # 11) проверка вместимости, только если нужно и есть пары
    if need_capacity_check and effective_pairs:
        table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
            crud,
            cafe_id=effective_cafe_id,
            tables_slots=effective_pairs,
            require_non_empty=False,
        )
        await validate_capacity(
            crud,
            table_ids=table_ids,
            guest_number=effective_guest_number,
        )

    # 12) Применение изменений
    return await create_or_update_booking(
        crud=crud,
        current_user_id=current_user_id,
        booking=current_booking,
        data=patch_data,
        tables_slots=incoming_pairs,
    )
