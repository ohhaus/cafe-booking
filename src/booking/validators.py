from datetime import date
import logging
from typing import List, Optional, TYPE_CHECKING, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.crud import booking_crud
from src.booking.lookup import (
    cafe_is_active,
    slots_existing_active_in_cafe,
    tables_existing_active_in_cafe,
)
from src.booking.schemas import BookingCreate, BookingUpdate
from src.cache.client import RedisCache
from src.common.exceptions import (
    ConflictException,
    ValidationErrorException,
)


if TYPE_CHECKING:
    from src.booking.services import EffectivePatch

logger = logging.getLogger('app')

Pair = Tuple[UUID, UUID]


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


async def validate_booking_create(
    session: AsyncSession,
    *,
    booking_data: BookingCreate,
    pairs: List[Pair],
    client_cache: RedisCache,
) -> None:
    """Валидирует данные для создания брони."""
    # 1. Проверка кафе
    await validate_cafe_exists(
        session,
        booking_data.cafe_id,
        client_cache,
    )

    # 2. Проверка столов и слотов
    table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
        session,
        cafe_id=booking_data.cafe_id,
        tables_slots=pairs,
        require_non_empty=True,
        client_cache=client_cache,
    )

    # 3) Проверка вместимости
    await validate_capacity(
        session,
        table_ids=table_ids,
        guest_number=booking_data.guest_number,
    )

    # 4) Проверка занятости
    await validate_table_slot_is_not_booked(
        session,
        tables_slots=pairs,
        booking_date=booking_data.booking_date,
        exclude_booking_id=None,
    )


async def validate_booking_update(
    session: AsyncSession,
    *,
    eff: 'EffectivePatch',
    booking_id: UUID,
    client_cache: RedisCache,
) -> None:
    """Валидирует данные для обновления брони."""
    # Проверка доступности столов
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
            exclude_booking_id=booking_id,
        )

    # Проверка вместимости
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
