from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cafes.models import Cafe
from src.slots.models import Slot
from src.slots.schemas import TimeSlotCreate, TimeSlotUpdate
from src.slots.utils import get_cafe_or_none, is_admin_or_manager
from src.users.models import User


async def list_slots(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    show_all: bool = False,
) -> Sequence[Slot]:
    """Список слотов кафе.

    ADMIN/MANAGER:
      - show_all=True  -> все слоты
      - show_all=False -> только активные

    USER:
      - только активные слоты
      - если кафе не активно — пустой список.
    """
    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        return []

    stmt = (
        select(Slot)
        .options(selectinload(Slot.cafe))
        .whete(Slot.cafe_id == cafe_id)
        .order_by(Slot.start_time)
    )

    if is_admin_or_manager(current_user):
        if not show_all:
            stmt = stmt.where(Slot.active.is_(True))
    else:
        if not cafe.active:
            return []
        stmt = stmt.where(Slot.active.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_slot(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    slot_id: UUID,
) -> Optional[Slot]:
    """Получение слота по UUID в рамках кафе."""
    stmt = (
        select(Slot)
        .options(selectinload(Slot.cafe))
        .where(Slot.id == slot_id, Slot.cafe_id == cafe_id)
    )

    if not is_admin_or_manager(current_user):
        stmt = (
            stmt.where(Slot.active.is_(True))
            .join(Slot.cafe)
            .where(Cafe.active.is_(True))
        )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_slot(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    data: TimeSlotCreate,
) -> Slot:
    """Создать слот в кафе.

    Только ADMIN/MANAGER.
    """
    if not is_admin_or_manager(current_user):
        raise PermissionError('Недостаточно прав для создания слота')

    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        raise LookupError('Кафе не найдено')

    slot = Slot(
        cafe_id=cafe_id,
        start_time=data.start_time,
        end_time=data.end_time,
        description=data.description,
    )

    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return slot


async def update_slot(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    slot_id: UUID,
    data: TimeSlotUpdate,
) -> Optional[Slot]:
    """Частично обновить слот."""
    if not is_admin_or_manager(current_user):
        raise PermissionError('Недостаточно прав для обновления слота')
    result = await db.execute(
        select(Slot)
        .options(selectinload(Slot.cafe))
        .where(Slot.id == slot_id, Slot.cafe_id == cafe_id),
    )
    slot = result.scalars().first()
    if not slot:
        return None

    payload = data.model_dump(exclude_unset=True)

    if 'is_active' in payload:
        slot.active = payload['is_active']

    if 'start_time' in payload:
        slot.start_time = payload['start_time']

    if 'end_time' in payload:
        slot.end_time = payload['end_time']

    if 'description' in payload:
        slot.description = payload['description']

    await db.commit()
    await db.refresh(slot)
    return slot
