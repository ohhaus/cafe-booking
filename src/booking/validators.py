from dataclasses import dataclass
from datetime import date
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.constants import BookingStatus
from src.booking.crud import booking_crud
from src.booking.lookup import (
    cafe_is_active,
    slots_existing_active_in_cafe,
    tables_existing_active_in_cafe,
)
from src.booking.models import Booking
from src.booking.schemas import BookingCreate, BookingUpdate
from src.booking.services import (
    cancel_or_restore_booking_service,
    create_or_update_booking_service,
)
from src.cache.client import RedisCache
from src.common.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationErrorException,
)
from src.users.models import User


logger = logging.getLogger('app')

Pair = Tuple[UUID, UUID]


@dataclass(frozen=True)
class EffectivePatch:
    """Контейнер для вычисленных эффективных значений при обновлении брони."""

    cafe_id: UUID
    booking_date: date
    guest_number: int
    replace_tables_slots: bool
    guest_number_changed: bool
    date_changed: bool
    current_active_pairs: List[Pair]
    incoming_pairs: Optional[List[Pair]]
    effective_pairs: List[Pair]
    pairs_to_check_taken: List[Pair]


async def _get_booking_with_access_check(
    session: AsyncSession,
    *,
    booking_id: UUID,
    current_user: User,
) -> Booking:
    current_booking = await booking_crud.get(id=booking_id, session=session)
    if not current_booking:
        raise NotFoundException('Бронирование не найдено.')

    is_staff = current_user.is_staff()
    if not is_staff and current_booking.user_id != current_user.id:
        raise ForbiddenException(
            'Недостаточно прав для изменения бронирования.',
        )

    return current_booking


async def _maybe_cancel_or_restore(
    session: AsyncSession,
    *,
    current_booking: Booking,
    patch_data: BookingUpdate,
) -> Optional[Booking]:
    if patch_data.status is None:
        return None

    new_status = patch_data.status
    old_status = current_booking.status

    if new_status == BookingStatus.CANCELED or (
        new_status != BookingStatus.CANCELED
        and old_status == BookingStatus.CANCELED
    ):
        return await cancel_or_restore_booking_service(
            session=session,
            booking=current_booking,
            incoming_data=patch_data,
        )

    return None


def _collect_current_active_pairs(current_booking: Booking) -> List[Pair]:
    return [
        (bts.table_id, bts.slot_id)
        for bts in current_booking.booking_table_slots
        if getattr(bts, 'is_active', True)
    ]


def _collect_incoming_pairs(patch_data: BookingUpdate) -> Optional[List[Pair]]:
    if patch_data.tables_slots is None:
        return None
    return [(ts.table_id, ts.slot_id) for ts in patch_data.tables_slots]


def _compute_effective_patch(
    *,
    current_booking: Booking,
    patch_data: BookingUpdate,
) -> EffectivePatch:
    effective_cafe_id: UUID = (
        patch_data.cafe_id
        if patch_data.cafe_id is not None
        else current_booking.cafe_id
    )
    effective_date: date = (
        patch_data.booking_date
        if patch_data.booking_date is not None
        else current_booking.booking_date
    )
    effective_guest_number: int = (
        patch_data.guest_number
        if patch_data.guest_number is not None
        else current_booking.guest_number
    )

    replace_tables_slots = patch_data.tables_slots is not None
    guest_number_changed = patch_data.guest_number is not None
    current_active_pairs = _collect_current_active_pairs(current_booking)
    incoming_pairs = _collect_incoming_pairs(patch_data)

    effective_pairs: List[Pair] = (
        incoming_pairs if incoming_pairs is not None else current_active_pairs
    )

    date_changed = effective_date != current_booking.booking_date

    pairs_to_check_taken: List[Pair] = []
    if date_changed:
        pairs_to_check_taken = effective_pairs
    elif replace_tables_slots and incoming_pairs is not None:
        pairs_to_check_taken = list(
            set(incoming_pairs) - set(current_active_pairs),
        )

    return EffectivePatch(
        cafe_id=effective_cafe_id,
        booking_date=effective_date,
        guest_number=effective_guest_number,
        replace_tables_slots=replace_tables_slots,
        guest_number_changed=guest_number_changed,
        date_changed=date_changed,
        current_active_pairs=current_active_pairs,
        incoming_pairs=incoming_pairs,
        effective_pairs=effective_pairs,
        pairs_to_check_taken=pairs_to_check_taken,
    )


async def validate_cafe_exists(
    session: AsyncSession,
    cafe_id: UUID,
    cache_client: RedisCache,
) -> None:
    """Проверяет, что кафе существует и активно, используя кэш."""
    cafe = await cafe_is_active(
        session,
        cache_client,
        cafe_id,
    )
    if not cafe:
        raise ValidationErrorException('Кафе не найдено или не активно.')


async def validate_tables_slots_exist_and_belong_to_cafe(
    session: AsyncSession,
    *,
    cafe_id: UUID,
    tables_slots: List[Pair],
    require_non_empty: bool,
    client_cache: RedisCache,
) -> List[UUID]:
    """Валидирует, что столы/слоты существуют, активны и принадлежат кафе.

    Возвращает table_ids (с повторами, как в исходных парах).
    """
    pairs = list(tables_slots or [])
    if require_non_empty and not pairs:
        raise ValidationErrorException(
            'Необходимо указать хотя бы один стол и слот.',
        )

    # Нечего проверять дальше
    if not pairs:
        return []

    unique_table_ids, unique_slot_ids = map(lambda x: set(x), zip(*pairs))

    # Проверка столов — передаём список ID
    existing_table_ids = await tables_existing_active_in_cafe(
        session=session,
        client_cache=client_cache,
        cafe_id=cafe_id,
        table_ids=unique_table_ids,
    )
    missing_table_ids = unique_table_ids - existing_table_ids
    if missing_table_ids:
        raise ValidationErrorException(
            'Следующие столы не найдены, не активны или не принадлежат кафе: '
            f'{missing_table_ids}',
        )

    # Проверка слотов — передаём список ID
    existing_slot_ids = await slots_existing_active_in_cafe(
        session=session,
        client_cache=client_cache,
        cafe_id=cafe_id,
        slot_ids=unique_slot_ids,
    )
    missing_slot_ids = unique_slot_ids - existing_slot_ids
    if missing_slot_ids:
        raise ValidationErrorException(
            'Следующие слоты не найдены, не активны или не принадлежат кафе: '
            f'{missing_slot_ids}',
        )

    return [table_id for (table_id, _) in pairs]


async def validate_capacity(
    session: AsyncSession,
    *,
    table_ids: List[UUID],
    guest_number: int,
) -> None:
    """Проверяет, что суммарная вместимость столов >= количества гостей."""
    if not table_ids:
        return

    ok = await booking_crud.check_capacity(
        session,
        list(table_ids),
        guest_number,
    )
    if not ok:
        raise ValidationErrorException(
            f'Количество гостей ({guest_number}) превышает вместимость '
            'столов.',
        )


async def validate_table_slot_is_not_booked(
    session: AsyncSession,
    *,
    tables_slots: List[Pair],
    booking_date: date,
    exclude_booking_id: Optional[UUID] = None,
) -> None:
    """Проверяет, что указанные пары стол-слот не заняты на дату."""
    pairs = list(tables_slots or [])
    if not pairs:
        return

    taken_pairs = await booking_crud.get_taken_table_slot_pairs(
        session=session,
        pairs=pairs,
        booking_date=booking_date,
        exclude_booking_id=exclude_booking_id,
    )

    if taken_pairs:
        conflicts = sorted(taken_pairs, key=lambda x: (str(x[0]), str(x[1])))

        # Человекочитаемый список конфликтов
        conflicts_text = ', '.join(
            f'(table_id={table_id}, slot_id={slot_id})'
            for table_id, slot_id in conflicts
        )

        raise ConflictException(
            'Столы и слоты уже забронированы на дату '
            f'{booking_date}: {conflicts_text}.',
        )


async def validate_and_create_booking(
    session: AsyncSession,
    booking_data: BookingCreate,
    current_user_id: UUID,
    client_cache: RedisCache,
) -> Booking | None:
    """Полная валидация и создание бронирования.

    Проверяет бизнес-логику, конфликты и вместимость, затем создает бронь.
    Возвращает созданный объект Booking.
    """
    # 1) Проверяем кафе
    await validate_cafe_exists(session, booking_data.cafe_id, client_cache)

    # 2) Проверяем столы и слоты
    tables_slots = [
        (ts.table_id, ts.slot_id) for ts in booking_data.tables_slots
    ]
    table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
        session=session,
        cafe_id=booking_data.cafe_id,
        tables_slots=tables_slots,
        require_non_empty=True,
        client_cache=client_cache,
    )

    # 3) Проверяем вместимость
    await validate_capacity(
        session=session,
        table_ids=table_ids,
        guest_number=booking_data.guest_number,
    )

    # 4) Проверяем занятость
    await validate_table_slot_is_not_booked(
        session=session,
        tables_slots=tables_slots,
        booking_date=booking_data.booking_date,
        exclude_booking_id=None,
    )

    # 5) Создание брони
    return await create_or_update_booking_service(
        session=session,
        current_user_id=current_user_id,
        booking=None,
        data=booking_data,
        tables_slots=tables_slots,
    )


def validate_patch_cafe_change_requires_tables_slots(
    *,
    incoming_data: BookingUpdate,
    current_cafe_id: UUID,
) -> None:
    """Запрещает изменение cafe_id без одновременного указания tables_slots."""
    if (
        incoming_data.cafe_id is not None
        and incoming_data.cafe_id != current_cafe_id
    ):
        if incoming_data.tables_slots is None:
            raise ValidationErrorException(
                'Изменение cafe_id возможно только при явной передаче '
                '"tables_slots" (списка столов и слотов) для нового кафе.',
            )


async def validate_and_update_booking(
    session: AsyncSession,
    booking_id: UUID,
    current_user: User,
    patch_data: BookingUpdate,
    client_cache: RedisCache,
) -> Booking:
    """Полная валидация и обновление бронирования.

    Проверяет бизнес-логику, конфликты и вместимость, затем обновляет бронь.
    Возвращает обновлённый объект Booking.
    """
    # Проверяем, есть ли установленные поля в модели
    if not patch_data.model_fields_set:
        raise BadRequestException('Пустой запрос: нет полей для обновления.')

    # 1) Получение брони с проверкой доступа
    current_booking = await _get_booking_with_access_check(
        session,
        booking_id=booking_id,
        current_user=current_user,
    )

    # 2) Обработка отмены или восстановления брони —> завершаем обработку
    canceled_restored = await _maybe_cancel_or_restore(
        session,
        current_booking=current_booking,
        patch_data=patch_data,
    )
    if canceled_restored is not None:
        return canceled_restored

    # 3) запрет смены cafe без tables_slots
    validate_patch_cafe_change_requires_tables_slots(
        incoming_data=patch_data,
        current_cafe_id=current_booking.cafe_id,
    )

    # 4) собираем и фиксируем effective значения
    eff = _compute_effective_patch(
        current_booking=current_booking,
        patch_data=patch_data,
    )
    # 5) проверка доступности столов
    if eff.pairs_to_check_taken:
        await validate_tables_slots_exist_and_belong_to_cafe(
            session=session,
            cafe_id=eff.cafe_id,
            tables_slots=eff.pairs_to_check_taken,
            require_non_empty=True,
            client_cache=client_cache,
        )
        await validate_table_slot_is_not_booked(
            session=session,
            tables_slots=eff.pairs_to_check_taken,
            booking_date=eff.booking_date,
            exclude_booking_id=current_booking.id,
        )

    # 6) проверка вместимости
    need_capacity_check = eff.guest_number_changed or eff.replace_tables_slots

    if need_capacity_check and eff.effective_pairs:
        table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
            session=session,
            cafe_id=eff.cafe_id,
            tables_slots=eff.effective_pairs,
            require_non_empty=False,
            client_cache=client_cache,
        )
        await validate_capacity(
            session=session,
            table_ids=table_ids,
            guest_number=eff.guest_number,
        )

    # 7) Применение изменений
    return await create_or_update_booking_service(
        session=session,
        current_user_id=current_user.id,
        booking=current_booking,
        data=patch_data,
        tables_slots=eff.incoming_pairs,
    )
