from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import logging
from typing import Any, Iterable, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.crud import booking_crud, booking_table_slot_crud
from src.booking.enums import BookingStatus
from src.booking.models import Booking
from src.booking.schemas import BookingCreate, BookingUpdate
from src.booking.validators import (
    validate_cafe_exists,
    validate_capacity,
    validate_patch_cafe_change_requires_tables_slots,
    validate_table_slot_is_not_booked,
    validate_tables_slots_exist_and_belong_to_cafe,
)
from src.cache.client import RedisCache
from src.common.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
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


class BookingService:
    """Сервис для управления бронированиями."""

    def __init__(self, session: AsyncSession, cache: RedisCache) -> None:
        """Инициализирует сервис с сессией БД и клиентом кэша.

        Args:
            session: Асинхронная сессия базы данных.
            cache: Клиент Redis для кэширования.

        """
        self.session = session
        self.client_cache = cache

    async def create_booking(
        self,
        booking_data: BookingCreate,
        current_user_id: UUID,
    ) -> Booking:
        """Создает бронирование с полной валидацией."""
        try:
            pairs: list[tuple[UUID, UUID]] = self._pairs_from_tables_slots(
                booking_data.tables_slots,
            )
            await self._validate_create(
                booking_data,
                pairs,
            )

            booking = await self._create_booking_row(
                booking_data=booking_data,
                current_user_id=current_user_id,
            )
            await self.session.flush()

            await self._sync_booking_table_slots(
                booking=booking,
                new_pairs=pairs,
                booking_date=booking.booking_date,
                is_create=True,
            )

            await self.session.commit()
            await self.session.refresh(
                booking,
                attribute_names=['booking_table_slots', 'user', 'cafe'],
            )
            logger.info(
                'Бронирование %s успешно создано',
                booking.id,
                extra={'user_id': str(current_user_id)},
            )
            return booking

        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                'create_booking failed (user_id=%s)',
                current_user_id,
            )
            raise

    async def update_booking(
        self,
        booking_id: UUID,
        current_user: User,
        patch_data: BookingUpdate,
    ) -> Booking:
        """Обновляет бронирование с полной валидацией."""
        # Проверяем, есть ли установленные поля в модели
        if not patch_data.model_fields_set:
            raise BadRequestException(
                'Пустой запрос: нет полей для обновления.',
            )

        try:
            # 1) Получение брони с проверкой доступа
            booking = await self.get_booking_by_id(
                booking_id=booking_id,
                current_user=current_user,
            )

            # 2) Обработка отмены или восстановления брони —> выходим
            if self._is_cancel_or_restore_transition(booking, patch_data):
                await self._apply_cancel_or_restore(booking, patch_data)
                await self.session.refresh(
                    booking,
                    attribute_names=['booking_table_slots', 'user', 'cafe'],
                )
                await self.session.commit()
                return booking

            # 3) запрет смены cafe без tables_slots
            validate_patch_cafe_change_requires_tables_slots(
                incoming_data=patch_data,
                current_cafe_id=booking.cafe_id,
            )

            # 4) вычисляем effective значения и валидируем
            eff = self._compute_effective_patch(
                current_booking=booking,
                patch_data=patch_data,
            )

            # 5) проверка доступности и вместимости столов
            await self._validate_update(eff=eff, booking_id=booking.id)

            # 4) применяем обновления
            self._apply_patch_to_booking(booking, patch_data)

            # 5) синхронизация связей, если tables_slots присутствует в запросе
            if eff.incoming_pairs is not None:
                await self._sync_booking_table_slots(
                    booking=booking,
                    new_pairs=eff.incoming_pairs,
                    booking_date=eff.booking_date,
                    is_create=False,
                )

            await self.session.commit()
            await self.session.refresh(
                booking,
                attribute_names=['booking_table_slots', 'user', 'cafe'],
            )
            return booking

        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                'update_booking failed (booking_id=%s, user_id=%s)',
                booking_id,
                getattr(current_user, 'id', None),
            )
            raise

    async def get_bookings(
        self,
        current_user: User,
        show_all: bool = False,
        cafe_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> List[Booking]:
        """Получение списка бронирований с фильтрацией по ролям и параметрам.

        - Для обычных пользователей: только свои бронирования.
        - Для staff: можно фильтровать по user_id и cafe_id.
        - show_all: показывать только активные (по умолчанию) или все.
        """
        filters = []

        if not current_user.is_staff():
            filters.append(Booking.user_id == current_user.id)
            show_all = False
            user_id = None

        if cafe_id is not None:
            filters.append(Booking.cafe_id == cafe_id)
        if user_id is not None:
            filters.append(Booking.user_id == user_id)
        if not show_all:
            filters.append(Booking.active.is_(True))

        relationships = [
            'user',
            'cafe',
            'booking_table_slots',
        ]
        order_by = [desc(Booking.booking_date), desc(Booking.created_at)]

        bookings = await booking_crud.get_multi(
            session=self.session,
            filters=filters,
            relationships=relationships,
            order_by=order_by,
        )
        if not bookings:
            raise NotFoundException('Бронирование не найдено.')

        return bookings

    async def get_booking_by_id(
        self,
        booking_id: UUID,
        current_user: User,
    ) -> Booking:
        """Получает бронирование по ID с учётом прав доступа."""
        booking = await booking_crud.get(session=self.session, id=booking_id)
        if not booking:
            raise NotFoundException('Бронирование не найдено.')

        if not current_user.is_staff() and booking.user_id != current_user.id:
            raise ForbiddenException('Доступ запрещен.')

        await self.session.refresh(
            booking,
            attribute_names=['booking_table_slots', 'user', 'cafe'],
        )
        return booking

    # -----------------------
    # Internal helpers
    # -----------------------
    @staticmethod
    def _pairs_from_tables_slots(tables_slots: Iterable[Any]) -> List[Pair]:
        """Извлекает пары (table_id, slot_id) из списка объектов."""
        return [(ts.table_id, ts.slot_id) for ts in tables_slots]

    async def _validate_create(
        self,
        booking_data: BookingCreate,
        pairs: list[Pair],
    ) -> None:
        """Выполняет все проверки при создании бронирования."""
        # 1. Проверка кафе
        await validate_cafe_exists(
            self.session,
            booking_data.cafe_id,
            self.client_cache,
        )

        # 2. Проверка столов и слотов
        table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
            self.session,
            cafe_id=booking_data.cafe_id,
            tables_slots=pairs,
            require_non_empty=True,
            client_cache=self.client_cache,
        )

        # 3) Проверка вместимости
        await validate_capacity(
            self.session,
            table_ids=table_ids,
            guest_number=booking_data.guest_number,
        )

        # 4) Проверка занятости
        await validate_table_slot_is_not_booked(
            self.session,
            tables_slots=pairs,
            booking_date=booking_data.booking_date,
            exclude_booking_id=None,
        )

    async def _validate_update(
        self,
        *,
        eff: EffectivePatch,
        booking_id: UUID,
    ) -> None:
        """Выполняет все проверки при обновлении бронирования."""
        # Проверка доступности столов
        if eff.pairs_to_check_taken:
            await validate_tables_slots_exist_and_belong_to_cafe(
                session=self.session,
                cafe_id=eff.cafe_id,
                tables_slots=eff.pairs_to_check_taken,
                require_non_empty=True,
                client_cache=self.client_cache,
            )
            await validate_table_slot_is_not_booked(
                session=self.session,
                tables_slots=eff.pairs_to_check_taken,
                booking_date=eff.booking_date,
                exclude_booking_id=booking_id,
            )

        # Проверка вместимости
        need_capacity_check = (
            eff.guest_number_changed or eff.replace_tables_slots
        )
        if need_capacity_check and eff.effective_pairs:
            table_ids = await validate_tables_slots_exist_and_belong_to_cafe(
                session=self.session,
                cafe_id=eff.cafe_id,
                tables_slots=eff.effective_pairs,
                require_non_empty=False,
                client_cache=self.client_cache,
            )
            await validate_capacity(
                session=self.session,
                table_ids=table_ids,
                guest_number=eff.guest_number,
            )

    async def _create_booking_row(
        self,
        *,
        booking_data: BookingCreate,
        current_user_id: UUID,
    ) -> Booking:
        """Создаёт запись бронирования в БД без связи со столами/слотами."""
        booking = await booking_crud.create(
            session=self.session,
            obj_in={
                'user_id': current_user_id,
                'cafe_id': booking_data.cafe_id,
                'booking_date': booking_data.booking_date,
                'guest_number': booking_data.guest_number,
                'note': booking_data.note or '',
                'status': booking_data.status,
            },
            commit=False,
        )

        self._apply_status_change(
            booking,
            booking_data.status,
            trigger_domain_events=False,
        )
        return booking

    def _apply_patch_to_booking(
        self,
        booking: Booking,
        patch_data: BookingUpdate,
    ) -> None:
        """Применяет изменения из patch_data к объекту бронирования."""
        if patch_data.cafe_id is not None:
            booking.cafe_id = patch_data.cafe_id
        if patch_data.booking_date is not None:
            booking.booking_date = patch_data.booking_date
        if patch_data.guest_number is not None:
            booking.guest_number = patch_data.guest_number
        if patch_data.note is not None:
            booking.note = patch_data.note or ''
        if patch_data.status is not None:
            self._apply_status_change(
                booking,
                patch_data.status,
                trigger_domain_events=True,
            )

    @staticmethod
    def _apply_status_change(
        booking: Booking,
        new_status: BookingStatus,
        *,
        trigger_domain_events: bool,
    ) -> None:
        """Применяет изменение статуса и обновляет активность."""
        old_status: BookingStatus = booking.status
        if new_status == old_status:
            return

        logger.info(
            'Запрос на изменение статуса: %s -> %s (booking_id=%s)',
            old_status,
            new_status,
            getattr(booking, 'id', None),
            extra={'user_id': str(getattr(booking, 'user_id', '')) or None},
        )

        booking.status = new_status
        booking.active = new_status != BookingStatus.CANCELED

        if not trigger_domain_events:
            return

        if new_status == BookingStatus.CANCELED:
            booking.cancel_booking()
        elif old_status == BookingStatus.CANCELED:
            booking.restore_booking()

    @staticmethod
    def _is_cancel_or_restore_transition(
        booking: Booking,
        patch_data: BookingUpdate,
    ) -> bool:
        """Проверяет, является ли переход отменой или восстановлением брони."""
        if patch_data.status is None:
            return False
        new_status = patch_data.status
        old_status = booking.status
        return (new_status == BookingStatus.CANCELED) or (
            old_status == BookingStatus.CANCELED
            and new_status != BookingStatus.CANCELED
        )

    async def _apply_cancel_or_restore(
        self,
        booking: Booking,
        patch_data: BookingUpdate,
    ) -> None:
        """Применяет отмену или восстановление брони с доменными событиями."""
        if patch_data.status is not None:
            self._apply_status_change(
                booking,
                patch_data.status,
                trigger_domain_events=True,
            )

        if 'note' in patch_data.model_fields_set:
            booking.note = patch_data.note or ''

        await self.session.flush()

    async def _sync_booking_table_slots(
        self,
        *,
        booking: Booking,
        new_pairs: list[Pair],
        booking_date: date,
        is_create: bool,
    ) -> None:
        """Создаёт/обновляет связи бронирования со столами и слотами.

        - Пары из new_pairs должны быть активными (если были — реактивируем).
        - Пары, отсутствующие в new_pairs — деактивируем.
        - Новые пары — создаём.
        """
        await self.session.refresh(
            booking,
            attribute_names=['booking_table_slots'],
        )

        existing_pairs: dict[Pair, list] = defaultdict(list)

        if not is_create:
            # Собираем все существующие пары (активные и неактивные)
            for bts in booking.booking_table_slots:
                existing_pairs[(bts.table_id, bts.slot_id)].append(bts)
            # Для всех существующих пар:
            #    - если пара нужна -> актуализируем дату, активируем
            #    - если пара не нужна -> деактивируем
            for pair, rows in existing_pairs.items():
                keep = pair in new_pairs
                for bts in rows:
                    if keep:
                        bts.booking_date = booking_date
                        if not bts.active:
                            bts.active = True
                    else:
                        if bts.active:
                            bts.active = False
        # Создаём недостающие пары
        for table_id, slot_id in new_pairs - existing_pairs.keys():
            await booking_table_slot_crud.create(
                session=self.session,
                obj_in={
                    'booking_id': booking.id,
                    'table_id': table_id,
                    'slot_id': slot_id,
                    'booking_date': booking_date,
                },
                commit=False,
            )

    @staticmethod
    def _collect_current_active_pairs(current_booking: Booking) -> List[Pair]:
        """Собирает текущие активные пары (table_id, slot_id) бронирования."""
        return [
            (bts.table_id, bts.slot_id)
            for bts in current_booking.booking_table_slots
            if bts.active
        ]

    @staticmethod
    def _collect_incoming_pairs(
        patch_data: BookingUpdate,
    ) -> Optional[List[Pair]]:
        """Извлекает пары (table_id, slot_id) из данных обновления."""
        if patch_data.tables_slots is None:
            return None
        return [(ts.table_id, ts.slot_id) for ts in patch_data.tables_slots]

    def _compute_effective_patch(
        self,
        *,
        current_booking: Booking,
        patch_data: BookingUpdate,
    ) -> EffectivePatch:
        """Вычисляет эффективные значения и необходимые проверки."""
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

        current_active_pairs = self._collect_current_active_pairs(
            current_booking,
        )
        incoming_pairs = self._collect_incoming_pairs(patch_data)

        effective_pairs: List[Pair] = (
            incoming_pairs
            if incoming_pairs is not None
            else current_active_pairs
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
