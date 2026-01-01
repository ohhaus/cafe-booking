from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.models import Booking, BookingTableSlot
from src.booking.schemas import BookingCreate, BookingUpdate
from src.database.service import DatabaseService
from src.tables.models import Table


class BookingCRUD(DatabaseService[Booking, BookingCreate, BookingUpdate]):
    """Слой доступа к данным для бронирований."""

    @staticmethod
    async def is_table_slot_taken(
        session: AsyncSession,
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

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def check_capacity(
        session: AsyncSession,
        table_ids: List[UUID],
        guest_number: int,
    ) -> bool:
        """Проверить, достаточно ли мест в выбранных столах для гостей."""
        result = await session.execute(
            select(func.sum(Table.count_place)).where(Table.id.in_(table_ids)),
        )
        total_seats = result.scalar() or 0
        return guest_number <= total_seats


booking_crud = BookingCRUD(Booking)
booking_table_slot_crud = BookingCRUD(BookingTableSlot)
