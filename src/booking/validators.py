from dataclasses import dataclass
from datetime import date
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from fastapi import HTTPException
from starlette import status

from src.booking.crud import BookingCRUD
from src.booking.schemas import BookingCreate
from src.users.models import User


logger = logging.getLogger('app')


async def validate_booking_db_constraints(
    crud: BookingCRUD,
    *,
    cafe_id: UUID,
    booking_date: date,
    guest_number: int,
    tables_slots: List[Tuple[UUID, UUID]],
    current_user: Optional[User] = None,
    exclude_booking_id: Optional[UUID] = None,
    check_taken: bool = True,
) -> None:
    """Единый async-валидатор БД для CREATE и PATCH."""
    # Кафе
    cafe = await crud.get_cafe(cafe_id)
    if not cafe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Кафе не найдено',
        )

    # tables_slots обязателен в "эффективном" наборе
    if not tables_slots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Необходимо указать хотя бы один стол и слот.',
        )

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
    if not await crud.check_capacity(list(unique_table_ids), guest_number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Количество гостей {guest_number} превышает вместимость '
            'столов',
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
                    extra={'user_id': getattr(current_user, 'id', None)},
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Стол {table_id} в слоте {slot_id} уже '
                    f'забронирован на {booking_date}',
                )


async def validate_booking_data(
    crud: BookingCRUD,
    booking_data: BookingCreate,
    current_user: User,
) -> None:
    """Выполняет все проверки данных перед созданием брони."""
    pairs = [(ts.table_id, ts.slot_id) for ts in booking_data.tables_slots]
    await validate_booking_db_constraints(
        crud,
        cafe_id=booking_data.cafe_id,
        booking_date=booking_data.booking_date,
        guest_number=booking_data.guest_number,
        tables_slots=pairs,
        current_user=current_user,
        exclude_booking_id=None,
        check_taken=True,
    )


async def validate_patch_effective_booking(
    crud: BookingCRUD,
    *,
    cafe_id: UUID,
    booking_date: date,
    guest_number: int,
    tables_slots: List[Tuple[UUID, UUID]],
    exclude_booking_id: Optional[UUID] = None,
    check_taken: bool = False,
) -> None:
    """Валидация данных для PATCH."""
    await validate_booking_db_constraints(
        crud,
        cafe_id=cafe_id,
        booking_date=booking_date,
        guest_number=guest_number,
        tables_slots=tables_slots,
        current_user=None,
        exclude_booking_id=exclude_booking_id,
        check_taken=check_taken,
    )


def normalize_tables_slots_to_pairs(
    tables_slots: Sequence[Any],
) -> List[Tuple[UUID, UUID]]:
    """Приводит tables_slots к списку пар (table_id, slot_id).

    Поддерживает элементы как pydantic-объекты с атрибутами table_id/slot_id,
    так и dict-ы с ключами 'table_id'/'slot_id'.
    """
    pairs: List[Tuple[UUID, UUID]] = []
    for ts in tables_slots:
        if hasattr(ts, 'table_id') and hasattr(ts, 'slot_id'):
            pairs.append((ts.table_id, ts.slot_id))
        else:
            # ожидаем dict-like
            pairs.append((ts['table_id'], ts['slot_id']))
    return pairs


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


@dataclass(frozen=True)
class PatchEffectiveData:
    """Финальные значения полей брони после применения PATCH-обновления."""

    cafe_id: UUID
    booking_date: date
    guest_number: int
    note: Optional[str]
    replace_tables_slots: bool
    pairs_list: List[Tuple[UUID, UUID]]


def build_patch_effective_data(
    incoming_data: Dict[str, Any],
    *,
    current_cafe_id: UUID,
    current_booking_date: date,
    current_guest_number: int,
    current_note: Optional[str],
    current_active_pairs: Iterable[Tuple[UUID, UUID]],
) -> PatchEffectiveData:
    """Формирует финальные значения полей после применения PATCH."""
    effective_cafe_id = incoming_data.get('cafe_id', current_cafe_id)
    effective_booking_date = incoming_data.get(
        'booking_date',
        current_booking_date,
    )
    effective_guest_number = incoming_data.get(
        'guest_number',
        current_guest_number,
    )
    effective_note = incoming_data.get('note', current_note)

    replace_tables_slots = 'tables_slots' in incoming_data

    if replace_tables_slots:
        pairs_list = normalize_tables_slots_to_pairs(
            incoming_data['tables_slots'],
        )
    else:
        pairs_list = list(current_active_pairs)

    return PatchEffectiveData(
        cafe_id=effective_cafe_id,
        booking_date=effective_booking_date,
        guest_number=effective_guest_number,
        note=effective_note,
        replace_tables_slots=replace_tables_slots,
        pairs_list=pairs_list,
    )


def compute_pairs_diff(
    *,
    existing_active_pairs: Set[Tuple[UUID, UUID]],
    incoming_pairs_list: List[Tuple[UUID, UUID]],
) -> Tuple[Set[Tuple[UUID, UUID]], Set[Tuple[UUID, UUID]]]:
    """Вычисляет разницу между текущими и новыми парами стол-слот."""
    incoming_pairs = set(incoming_pairs_list)
    new_pairs = incoming_pairs - existing_active_pairs
    return incoming_pairs, new_pairs


def select_pairs_to_check(
    *,
    date_changed: bool,
    replace_tables_slots: bool,
    incoming_pairs: Set[Tuple[UUID, UUID]],
    new_pairs: Set[Tuple[UUID, UUID]],
) -> Set[Tuple[UUID, UUID]]:
    """Определяет, какие пары стол-слот нужно проверить на занятость."""
    if date_changed:
        return incoming_pairs
    if replace_tables_slots:
        return new_pairs
    return set()
