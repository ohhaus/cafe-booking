from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, Optional, Tuple, Union
from uuid import UUID

from src.booking.constants import BookingStatus
from src.booking.crud import BookingCRUD
from src.booking.models import Booking
from src.booking.schemas import BookingCreate, BookingUpdate


Pair = Tuple[UUID, UUID]
BookingIn = Union[BookingCreate, BookingUpdate]


def apply_status_is_active(
    booking: Booking,
    data: Dict[str, Any],
    *,
    trigger_domain_events: bool,
) -> None:
    """Применяет status и синхронизирует активность (booking.active).

    - status определяет active:
        - CANCELED (1) -> active = False
        - иначе -> active = True
    - Доменные методы cancel_booking()/restore_booking() вызываются только при
    UPDATE, и только при переходах:
        - X -> CANCELED
        - CANCELED -> X (X != CANCELED)
    """
    if not trigger_domain_events:
        return

    if 'status' not in data or data['status'] is None:
        return

    new_status: BookingStatus = data['status']
    old_status: BookingStatus = booking.status

    if new_status == old_status:
        return

    booking.status = new_status
    booking.active = new_status != BookingStatus.CANCELED

    if new_status == BookingStatus.CANCELED:
        booking.cancel_booking()
    elif old_status == BookingStatus.CANCELED:
        booking.restore_booking()


async def create_or_update_booking(
    *,
    crud: BookingCRUD,
    current_user_id: UUID,
    booking: Booking | None,
    data: BookingIn,
    tables_slots: Optional[Iterable[Pair]] = None,
) -> Booking:
    """Upsert бронирования.

    - Если booking=None: создаёт Booking.
    - Если booking задан: обновляет поля Booking.
    - tables_slots:
        - None: связи BookingTableSlot не меняем
        - iterable пар (table_id, slot_id): заменяем набор активных связей
    """
    # "Эффективные" значения для простых полей:
    # Обновляем все поля для POST запроса.
    if booking is None:
        cafe_id = data.cafe_id
        booking_date = data.booking_date
        guest_number = data.guest_number
        note = data.note or ''
        status = data.status

        booking = await crud.create_booking(
            user_id=current_user_id,
            cafe_id=cafe_id,
            guest_number=guest_number,
            note=note,
            status=status,
            booking_date=booking_date,
        )
    else:
        # Обновляем только то, что реально пришло в PATCH.
        if getattr(data, 'cafe_id', None) is not None:
            booking.cafe_id = data.cafe_id
        if getattr(data, 'booking_date', None) is not None:
            booking.booking_date = data.booking_date
        if getattr(data, 'guest_number', None) is not None:
            booking.guest_number = data.guest_number
        if getattr(data, 'note', None) is not None:
            booking.note = data.note or ''
        apply_status_is_active(
            booking,
            {'status': getattr(data, 'status', None)},
            trigger_domain_events=True,
        )

    if tables_slots is not None:
        await _create_or_update_booking_table_slots(
            crud=crud,
            booking=booking,
            pairs=set(tables_slots),
            booking_date=booking.booking_date,
        )

    return booking


async def _create_or_update_booking_table_slots(
    *,
    crud: BookingCRUD,
    booking: Booking,
    pairs: set[Pair],
    booking_date: date,
) -> None:
    """Создаёт или обновляет связи бронирования со столами и слотами.

    Активные пары (table_id, slot_id) из `pairs` обновляются
    (восстанавливаются, если были удалены).
    Отсутствующие активные пары деактивируются.
    Новые пары создаются.
    """
    # Явно загружаем booking_table_slots, чтобы избежать lazy loading
    # в асинхронном контексте
    await crud.db.refresh(booking, attribute_names=['booking_table_slots'])

    # Индексируем существующие связи по паре (table_id, slot_id)
    existing_by_pair: dict[Pair, list] = {}
    for bts in booking.booking_table_slots:
        (
            existing_by_pair.setdefault(
                (bts.table_id, bts.slot_id),
                [],
            ).append(bts)
        )

    # 1) Для всех существующих связей:
    #    - если пара нужна -> актуализируем дату, активируем (restore)
    #    - если пара не нужна -> деактивируем (soft_delete)
    for pair, rows in existing_by_pair.items():
        keep = pair in pairs
        for bts in rows:
            if keep:
                bts.booking_date = booking_date
                if not bts.active:
                    bts.active = True
            else:
                if bts.active:
                    bts.active = False

    # 2) Создаём недостающие пары
    for table_id, slot_id in pairs:
        if (table_id, slot_id) not in existing_by_pair:
            await crud.create_booking_slot(
                booking_id=booking.id,
                table_id=table_id,
                slot_id=slot_id,
                booking_date=booking_date,
            )
