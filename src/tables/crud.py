from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cafes.models import Cafe
from src.tables.models import Table
from src.tables.schemas import TableCreate, TableUpdate
from src.tables.utils import get_cafe_or_none, is_admin_or_manager
from src.users.models import User


async def list_tables(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    show_all: bool = False,
) -> Sequence[Table]:
    """Получить список столов для кафе.

    Поведение по ролям:
      - ADMIN/MANAGER:
          * show_all=True  -> все столы кафе (active и не active)
          * show_all=False -> только активные столы (active=True)
      - USER:
          * всегда только активные столы (active=True)
          * если кафе не активно — вернуть пустой список (как “нет доступных”)

    Возвращает:
      - список объектов Table (может быть пустым).
    """
    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        return []

    stmt = (
        select(Table)
        .options(selectinload(Table.cafe))
        .where(Table.cafe_id == cafe_id)
        .order_by(Table.created_at.desc())
    )

    if is_admin_or_manager(current_user):
        if not show_all:
            stmt = stmt.where(Table.active.is_(True))
    else:
        if not cafe.active:
            return []
        stmt = stmt.where(Table.active.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_table(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    table_id: UUID,
) -> Optional[Table]:
    """Получить информацию о конкретном столе в кафе по его id.

    Поведение по ролям:
      - ADMIN/MANAGER: видят стол независимо от active
        (если он в указанном кафе)
      - USER: видит только если и кафе active=True, и стол active=True

    Возвращает:
      - Table, если найден и доступен по правилам,
      - None, если не найден или недоступен (роутер решит: 404/403).
    """
    stmt = (
        select(Table)
        .options(selectinload(Table.cafe))
        .where(Table.id == table_id, Table.cafe_id == cafe_id)
    )
    if not is_admin_or_manager(current_user):
        stmt = (
            stmt.where(Table.active.is_(True))
            .join(Table.cafe)
            .where(Cafe.active.is_(True))
        )

    result = await db.execute(stmt)
    return result.scalars().first()


async def create_table(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    data: TableCreate,
) -> Table:
    """Создать новый стол в кафе.

    Доступ:
      - только ADMIN/MANAGER

    Валидация:
      - кафе должно существовать
      - seat_number из API кладём в count_place модели

    Ошибки:
      - PermissionError: если нет прав (роутер -> 403)
      - LookupError: если кафе не найдено (роутер -> 404)
    """
    if not is_admin_or_manager(current_user):
        raise PermissionError('Недостаточно прав для создания стола')

    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        raise LookupError('Кафе не найдено')

    table = Table(
        cafe_id=cafe_id,
        description=data.description,
        count_place=data.seat_number,  # API -> DB
    )

    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table


async def update_table(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    table_id: UUID,
    data: TableUpdate,
) -> Table | None:
    """Частично обновить стол в кафе (PATCH).

    Доступ:
      - только ADMIN/MANAGER

    Обновляемые поля:
      - description
      - seat_number (маппим в count_place)
      - is_active (маппим в active)

    Возвращает:
      - обновлённый Table, если найден,
      - None, если стол/кафе-связка не найдены (роутер -> 404).

    Ошибки:
      - PermissionError: если нет прав (роутер -> 403).
    """
    if not is_admin_or_manager(current_user):
        raise PermissionError('Недостаточно прав для обновления стола')

    result = await db.execute(
        select(Table)
        .options(selectinload(Table.cafe))
        .where(Table.id == table_id, Table.cafe_id == cafe_id),
    )
    table = result.scalars().first()
    if not table:
        return None

    payload = data.model_dump(exclude_unset=True)

    # is_active (API) -> active (DB)
    if 'is_active' in payload:
        table.active = payload['is_active']

    if 'description' in payload:
        table.description = payload['description']

    # seat_number (API) -> count_place (DB)
    if 'seat_number' in payload:
        table.count_place = payload['seat_number']

    await db.commit()
    await db.refresh(table)
    return table
