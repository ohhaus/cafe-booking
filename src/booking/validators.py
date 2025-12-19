from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
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
            'BOOKING (0) или ACTIVE (2).',
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


async def validate_patch_effective_booking(
    crud: BookingCRUD,
    *,
    cafe_id: UUID,
    booking_date: date,
    guest_number: int,
    tables_slots: List[Tuple[UUID, UUID]],
) -> None:
    """Валидация данных для PATCH."""
    # 1) Дата
    today = date.today()
    max_date = today + timedelta(days=MAX_BOOKING_DATE)
    if not (today <= booking_date <= max_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                'Дата бронирования должна быть в диапазоне от сегодня '
                f'до {MAX_BOOKING_DATE} дней вперёд.'
            ),
        )

    # 2) Кафе
    cafe = await crud.get_cafe(cafe_id)
    if not cafe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Кафе не найдено',
        )

    # 3) tables_slots обязателен в "эффективном" наборе
    if not tables_slots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Необходимо указать хотя бы один стол и слот.',
        )

    # 4) Уникальность пар table_id+slot_id в запросе
    if len(set(tables_slots)) != len(tables_slots):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Повторяющиеся (table_id, slot_id) в tables_slots '
            'недопустимы.',
        )

    table_ids = [table for (table, _) in tables_slots]
    slot_ids = [slot for (_, slot) in tables_slots]

    # 5) Столы
    tables = await crud.get_tables(table_ids, cafe_id)
    if len(tables) != len(table_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Один или более столов не найдено или не активны.',
        )

    # 6) Слоты
    slots = await crud.get_slots(slot_ids, cafe_id)
    if len(slots) != len(slot_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Один или более слотов не найдено или не активны.',
        )

    # 7) Вместимость
    if not await crud.check_capacity(table_ids, guest_number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Количество гостей превышает вместимость столов',
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
        if ts is None:
            continue
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
        if (not tables_in_payload) or (
            incoming_data.get('tables_slots') is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    'Изменение cafe_id возможно только при явной передаче '
                    '"tables_slots" (списка столов и слотов) для нового кафе.'
                ),
            )


def validate_patch_status_is_active_consistency(
    *,
    incoming_data: dict,
) -> None:
    """Проверка согласованности status и is_active."""
    if 'status' not in incoming_data or incoming_data.get('status') is None:
        return
    if (
        'is_active' not in incoming_data
        or incoming_data.get('is_active') is None
    ):
        return

    new_status: BookingStatus = incoming_data['status']
    new_is_active: bool = bool(incoming_data['is_active'])

    if new_status == BookingStatus.CANCELED and new_is_active is True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Нельзя одновременно установить status=CANCELED и '
            'is_active=true.',
        )
    if new_status != BookingStatus.CANCELED and new_is_active is False:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                'Нельзя одновременно установить status!=CANCELED и '
                'is_active=false. '
                'Либо отмените бронь через status=CANCELED, либо '
                'не передавайте is_active.'
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


def validate_patch_not_empty(incoming_data: Dict[str, Any]) -> None:
    """Проверяет, что запрос на обновление не пуст."""
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Пустой запрос: нет полей для обновления.',
        )


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
