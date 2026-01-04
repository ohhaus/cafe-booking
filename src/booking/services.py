from __future__ import annotations

from collections import defaultdict
from datetime import date
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.constants import BookingStatus
from src.booking.crud import booking_crud, booking_table_slot_crud
from src.booking.models import Booking
from src.booking.schemas import BookingCreate, BookingUpdate
from src.cache.client import RedisCache
from src.celery.tasks.admin_events import notify_admins_about_event
from src.common.exceptions import ForbiddenException, NotFoundException
from src.users.models import User


logger = logging.getLogger('app')

Pair = Tuple[UUID, UUID]
BookingIn = Union[BookingCreate, BookingUpdate]


class BookingValidationService:
    """Сервис валидации бронирований с внедрением зависимостей."""

    def __init__(
        self,
        session: AsyncSession,
        client_cache: RedisCache,
    ) -> None:
        """Инициализирует сервис с сессией БД и клиентом кэша.

        Args:
            session: Асинхронная сессия базы данных.
            client_cache: Клиент Redis для кэширования.

        """
        self.session = session
        self.client_cache = client_cache

    async def validate_and_create_booking(
        self,
        data: BookingCreate,
        current_user_id: UUID,
    ) -> Booking:
        """Выполняет валидацию и создание новой брони."""
        from src.booking.validators import validate_and_create_booking

        return await validate_and_create_booking(
            session=self.session,
            booking_data=data,
            current_user_id=current_user_id,
            client_cache=self.client_cache,
        )

    async def validate_and_update_booking(
        self,
        booking_id: UUID,
        current_user: User,
        patch_data: BookingUpdate,
    ) -> Booking:
        """Выполняет валидацию и обновление брони с учётом зависимостей."""
        from src.booking.validators import validate_and_update_booking

        return await validate_and_update_booking(
            session=self.session,
            booking_id=booking_id,
            current_user=current_user,
            patch_data=patch_data,
            client_cache=self.client_cache,
        )


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

    logger.info(
        'Запрос на изменение статуса: %s -> %s (booking_id=%s)',
        old_status,
        new_status,
        getattr(booking, 'id', None),
        extra={'user_id': str(getattr(booking, 'user_id', '')) or None},
    )

    booking.status = new_status
    booking.active = new_status != BookingStatus.CANCELED

    if new_status == BookingStatus.CANCELED:
        booking.cancel_booking()
    elif old_status == BookingStatus.CANCELED:
        booking.restore_booking()


async def create_or_update_booking_service(
    session: AsyncSession,
    *,
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
    try:
        is_create = booking is None
        if booking is None:
            # Обработка создания бронирования.
            booking = await booking_crud.create(
                session=session,
                obj_in={
                    'user_id': current_user_id,
                    'cafe_id': data.cafe_id,
                    'booking_date': data.booking_date,
                    'guest_number': data.guest_number,
                    'note': data.note or '',
                    'status': data.status,
                },
                commit=False,
            )
            await session.flush()

            logger.info(
                'Создано бронирование: (booking_id=%s, cafe_id=%s, date=%s)',
                booking.id,
                booking.cafe_id,
                booking.booking_date,
                extra={'user_id': str(current_user_id)},
            )

        else:
            # Обработка обновления бронирования.
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
            await booking_crud.update(
                session=session,
                db_obj=booking,
                obj_in={
                    'user_id': current_user_id,
                    'cafe_id': booking.cafe_id,
                    'booking_date': booking.booking_date,
                    'guest_number': booking.guest_number,
                    'note': booking.note or '',
                    'status': booking.status,
                },
                commit=False,
            )

            logger.info(
                'Бронирование обновлено: (booking_id=%s, cafe_id=%s, date=%s)',
                booking.id,
                booking.cafe_id,
                booking.booking_date,
                extra={'user_id': str(current_user_id)},
            )

        if tables_slots is not None:
            await _create_or_update_booking_table_slots(
                session=session,
                booking=booking,
                new_pairs=set(tables_slots),
                booking_date=booking.booking_date,  # type: ignore
                is_create=is_create,
            )

        await session.commit()
        try:
            event = 'created' if is_create else 'updated'

            notify_admins_about_event.delay(
                str(booking.id),
                event,
                {
                    'message': (
                        'Создана новая бронь'
                        if is_create
                        else 'Бронь обновлена'
                    ),
                },
            )
        except Exception:
            logger.exception(
                'Не удалось поставить Celery-задачи после commit '
                '(booking_id=%s, is_create=%s)',
                getattr(booking, 'id', None),
                is_create,
            )
        return booking

    except SQLAlchemyError:
        await session.rollback()
        logger.error(
            'Создание/обновление бронирования не удалось, rolled back '
            '(is_create=%s, booking_id=%s)',
            is_create,  # noqa
            getattr(booking, 'id', None),
            extra={'user_id': str(current_user_id)},
            exc_info=True,
        )
        raise


async def _create_or_update_booking_table_slots(
    session: AsyncSession,
    *,
    booking: Booking,
    new_pairs: set[Pair],
    booking_date: date,
    is_create: bool,
) -> None:
    """Создаёт или обновляет связи бронирования со столами и слотами.

    Активные пары (table_id, slot_id) из `pairs` обновляются
    (восстанавливаются, если были удалены).
    Отсутствующие активные пары деактивируются.
    Новые пары создаются.
    """
    # Явно загружаем booking_table_slots, чтобы избежать
    # lazy loading в асинхронном контексте
    await session.refresh(
        booking,
        attribute_names=['booking_table_slots'],
    )
    existing_pairs: dict[Pair, list] = defaultdict(list)
    if not is_create:
        # Собираем все существующие пары (активные и неактивные)
        for bts in booking.booking_table_slots:
            existing_pairs[(bts.table_id, bts.slot_id)].append(bts)

        # 1) Для всех существующих пар:
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

    # 2) Создаём недостающие пары
    for table_id, slot_id in new_pairs - existing_pairs.keys():
        await booking_table_slot_crud.create(
            session=session,
            obj_in={
                'booking_id': booking.id,
                'table_id': table_id,
                'slot_id': slot_id,
                'booking_date': booking_date,
            },
            commit=False,
        )


async def get_bookings_service(
    session: AsyncSession,
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
        session=session,
        filters=filters,
        relationships=relationships,
        order_by=order_by,
    )
    if not bookings:
        raise NotFoundException('Бронирование не найдено.')

    return bookings


async def get_booking_by_id_service(
    session: AsyncSession,
    booking_id: UUID,
    current_user: User,
    is_staff: bool,
) -> Booking:
    """Получает бронирование по ID с учётом прав доступа."""
    if not is_staff:
        booking = await booking_crud.get(
            session=session,
            id=booking_id,
        )
        if booking and booking.user_id != current_user.id:
            raise ForbiddenException('Доступ запрещен.')
    else:
        booking = await booking_crud.get(
            session=session,
            id=booking_id,
        )
    if not booking:
        raise NotFoundException('Бронирование не найдено.')

    await session.refresh(
        booking,
        attribute_names=['booking_table_slots', 'user', 'cafe'],
    )

    return booking


async def cancel_or_restore_booking_service(
    session: AsyncSession,
    booking: Booking,
    incoming_data: BookingUpdate,
) -> Booking:
    """Отменяет или восстанавливает бронь в зависимости от статуса."""
    new_status: BookingStatus | None = incoming_data.status

    if new_status == BookingStatus.CANCELED:
        booking.cancel_booking()
    else:
        booking.restore_booking()

    if 'note' in incoming_data:
        booking.note = incoming_data.note

    try:
        await booking_crud.update(
            session=session,
            db_obj=booking,
            obj_in={
                'status': booking.status,
                'active': booking.active,
                'note': booking.note,
            },
            commit=False,
        )
        await session.commit()
        try:
            event = (
                'canceled'
                if new_status == BookingStatus.CANCELED
                else 'restored'
            )

            notify_admins_about_event.delay(
                str(booking.id),
                event,
                {
                    'message': (
                        'Бронь отменена'
                        if event == 'canceled'
                        else 'Бронь восстановлена'
                    ),
                },
            )
        except Exception:
            logger.exception(
                'Не удалось поставить Celery-задачу после commit '
                '(booking_id=%s, event=%s)',
                booking.id,
                (
                    'canceled'
                    if new_status == BookingStatus.CANCELED
                    else 'restored'
                ),
            )
        return booking
    except SQLAlchemyError:
        await session.rollback()
        logger.error(
            'Отмена/восстановление бронирования не удалось, rolled back '
            '(booking_id=%s)',
            booking.id,
            extra={'user_id': str(getattr(booking, 'user_id', '')) or None},
            exc_info=True,
        )
        raise
