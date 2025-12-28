from datetime import date
from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.booking.constants import BookingStatus
from src.booking.models import Booking, BookingTableSlot
from src.cafes.models import Cafe
from src.slots.models import Slot
from src.tables.models import Table


class BookingCRUD:
    """Слой доступа к данным для бронирований."""

    def __init__(self, db: AsyncSession) -> None:
        """Инициализация CRUD с асинхронной сессией."""
        self.db = db

    async def get_cafe(self, cafe_id: UUID) -> Optional[Cafe]:
        """Получить кафе по ID, если оно активно."""
        result = await self.db.execute(
            select(Cafe).where(
                Cafe.id == cafe_id,
                Cafe.active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def get_tables(
        self,
        table_ids: List[UUID],
        cafe_id: UUID,
    ) -> Sequence[Table]:
        """Получить список активных столов по ID и привязке к кафе."""
        if not table_ids:
            return []

        result = await self.db.execute(
            select(Table).where(
                Table.id.in_(table_ids),
                Table.cafe_id == cafe_id,
                Table.active.is_(True),
            ),
        )
        return result.scalars().all()

    async def get_slots(
        self,
        slot_ids: List[UUID],
        cafe_id: UUID,
    ) -> Sequence[Slot]:
        """Получить список активных временных слотов по ID."""
        if not slot_ids:
            return []
        result = await self.db.execute(
            select(Slot).where(
                Slot.id.in_(slot_ids),
                Slot.cafe_id == cafe_id,
                Slot.active.is_(True),
            ),
        )
        return result.scalars().all()

    async def is_table_slot_taken(
        self,
        table_id: UUID,
        slot_id: UUID,
        booking_date: date,
        exclude_booking_id: Optional[UUID] = None,
    ) -> bool:
        """Проверить, занят ли стол в указанный временной слот на дату."""
        stmt = (
            select(1)
            .select_from(BookingTableSlot)
            .where(
                BookingTableSlot.table_id == table_id,
                BookingTableSlot.slot_id == slot_id,
                BookingTableSlot.booking_date == booking_date,
                BookingTableSlot.active.is_(True),
            )
            .limit(1)
        )

        if exclude_booking_id is not None:
            stmt = stmt.where(
                BookingTableSlot.booking_id != exclude_booking_id,
            )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def check_capacity(
        self,
        table_ids: List[UUID],
        guest_number: int,
    ) -> bool:
        """Проверить, достаточно ли мест в выбранных столах для гостей."""
        result = await self.db.execute(
            select(func.sum(Table.count_place)).where(Table.id.in_(table_ids)),
        )
        total_seats = result.scalar() or 0
        return guest_number <= total_seats

    async def create_booking(
        self,
        user_id: UUID,
        cafe_id: UUID,
        guest_number: int,
        note: Optional[str],
        status: BookingStatus,
        booking_date: date,
    ) -> Booking:
        """Создать новую запись бронирования."""
        booking = Booking(
            user_id=user_id,
            cafe_id=cafe_id,
            guest_number=guest_number,
            note=note or '',
            status=status,
            booking_date=booking_date,
            active=True,
        )
        self.db.add(booking)
        await self.db.flush()
        return booking

    async def create_booking_slot(
        self,
        booking_id: UUID,
        table_id: UUID,
        slot_id: UUID,
        booking_date: date,
    ) -> None:
        """Создать запись связи брони со столом и слотом."""
        booking_slot = BookingTableSlot(
            booking_id=booking_id,
            table_id=table_id,
            slot_id=slot_id,
            booking_date=booking_date,
            active=True,
        )
        self.db.add(booking_slot)

    async def get_bookings(
        self,
        current_user_id: UUID,
        show_all: bool,
        is_staff: bool,
        cafe_id: Optional[UUID],
        user_id: Optional[UUID],
    ) -> Sequence[Booking]:
        """Получить список бронирований с фильтрацией по ролям пользователя."""
        query = select(Booking).options(
            selectinload(Booking.user),
            selectinload(Booking.cafe),
            selectinload(Booking.booking_table_slots).selectinload(
                BookingTableSlot.table,
            ),
            selectinload(Booking.booking_table_slots).selectinload(
                BookingTableSlot.slot,
            ),
        )

        # Ограничение доступа
        if not is_staff:
            query = query.where(Booking.user_id == current_user_id)
            show_all = False
            user_id = None

        # Фильтры
        if cafe_id is not None:
            query = query.where(Booking.cafe_id == cafe_id)
        if is_staff and user_id is not None:
            query = query.where(Booking.user_id == user_id)

        # Активность
        if not show_all:
            query = query.where(Booking.active.is_(True))

        query = query.order_by(
            Booking.booking_date.desc(),
            Booking.created_at.desc(),
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_booking_by_id(
        self,
        booking_id: UUID,
        *,
        current_user_id: UUID,
        is_staff: bool,
    ) -> Optional[Booking]:
        """Получить бронирование по ID с проверкой прав доступа."""
        query = (
            select(Booking)
            .where(Booking.id == booking_id)
            .options(
                selectinload(Booking.user),
                selectinload(Booking.cafe),
                selectinload(Booking.booking_table_slots).selectinload(
                    BookingTableSlot.table,
                ),
                selectinload(Booking.booking_table_slots).selectinload(
                    BookingTableSlot.slot,
                ),
            )
        )

        if not is_staff:
            query = query.where(Booking.user_id == current_user_id)

        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()
