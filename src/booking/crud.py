from datetime import date
from typing import Any, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.models import Booking, BookingStatus, BookingTableSlot
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
                Cafe.active,
            ),
        )
        return result.scalar_one_or_none()

    async def get_tables(
        self,
        table_ids: List[UUID],
        cafe_id: UUID,
    ) -> Sequence[Any]:
        """Получить список активных столов по ID и привязке к кафе."""
        result = await self.db.execute(
            select(Table).where(
                Table.id.in_(table_ids),
                Table.cafe_id == cafe_id,
                Table.active,
            ),
        )
        return result.scalars().all()

    async def get_slots(
        self,
        slot_ids: List[UUID],
        cafe_id: UUID,
    ) -> Sequence[Any]:
        """Получить список активных временных слотов по ID."""
        result = await self.db.execute(
            select(Slot).where(
                Slot.id.in_(slot_ids),
                Slot.cafe_id == cafe_id,
                Slot.active,
            ),
        )
        return result.scalars().all()

    async def is_slot_taken(
        self,
        table_id: UUID,
        slot_id: UUID,
        booking_date: date,
    ) -> bool:
        """Проверить, занят ли стол в указанный временной слот на дату."""
        conflict_query = (
            exists()
            .where(
                and_(
                    BookingTableSlot.table_id == table_id,
                    BookingTableSlot.slot_id == slot_id,
                    BookingTableSlot.booking_date == booking_date,
                    BookingTableSlot.active,
                ),
            )
            .select()
        )

        result = await self.db.execute(conflict_query)
        return result.scalar()

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
