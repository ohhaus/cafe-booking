from datetime import date
from typing import List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.models import Booking, BookingTableSlot
from src.booking.schemas import BookingCreate, BookingUpdate
from src.database.service import DatabaseService
from src.tables.models import Table


Pair = Tuple[UUID, UUID]


class BookingCRUD(DatabaseService[Booking, BookingCreate, BookingUpdate]):
    """Слой доступа к данным для бронирований."""

    @staticmethod
    async def get_taken_table_slot_pairs(
        session: AsyncSession,
        *,
        pairs: List[Pair],
        booking_date: date,
        exclude_booking_id: Optional[UUID] = None,
    ) -> Set[Pair]:
        """Вернуть множество занятых пар (table_id, slot_id) на дату."""
        if not pairs:
            return set()

        unique_pairs = list(dict.fromkeys(pairs))

        stmt = select(
            BookingTableSlot.table_id,
            BookingTableSlot.slot_id,
        ).where(
            BookingTableSlot.booking_date == booking_date,
            BookingTableSlot.active.is_(True),
            tuple_(BookingTableSlot.table_id, BookingTableSlot.slot_id).in_(
                unique_pairs,
            ),
        )

        if exclude_booking_id is not None:
            stmt = stmt.where(
                BookingTableSlot.booking_id != exclude_booking_id,
            )

        result = await session.execute(stmt)
        rows = result.all()  # list[Row[(UUID, UUID)]]
        return {(table_id, slot_id) for table_id, slot_id in rows}

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
