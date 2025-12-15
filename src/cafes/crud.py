from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cafes.models import Cafe
from src.cafes.schemas import CafeCreate, CafeUpdate
from src.cafes.service import sync_cafe_managers
from src.users.models import User, UserRole


async def get_cafes_list(
    db: AsyncSession,
    current_user: User,
    show_all: bool = False,
) -> Sequence[Cafe]:
    """Получение списка кафе с учетом роли пользователя и флагом show_all."""
    stmt = (
        select(Cafe)
        .options(selectinload(Cafe.managers))
        .order_by(Cafe.created_at.desc())
    )
    is_admin_or_manager = current_user.role in {
        UserRole.ADMIN,
        UserRole.MANAGER,
    }
    if is_admin_or_manager:
        if not show_all:
            stmt = stmt.where(Cafe.active.is_(True))
    else:
        stmt = stmt.where(Cafe.active.is_(True))

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_cafe_by_id(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
) -> Optional[Cafe]:
    """Получение информации о кафе с учетом роли пользователя."""
    stmt = (
        select(Cafe)
        .options(selectinload(Cafe.managers))
        .where(Cafe.id == cafe_id)
    )
    is_admin_or_manager = current_user.role in {
        UserRole.ADMIN,
        UserRole.MANAGER,
    }
    if not is_admin_or_manager:
        stmt = stmt.where(Cafe.active.is_(True))

    result = await db.execute(stmt)
    return result.scalars().first()


async def create_cafe(
    db: AsyncSession,
    current_user: User,
    data: CafeCreate,
) -> Cafe:
    """Создание нового кафе."""
    if current_user.role not in {
        UserRole.ADMIN,
        UserRole.MANAGER,
    }:
        raise PermissionError(
            'Недостаточно прав для обновления кафе.',
        )
    cafe = Cafe(
        name=data.name,
        address=data.address,
        phone=str(data.phone),
        description=data.description,
        photo_id=data.photo_id,
    )
    await db.add(cafe)
    await db.flush()

    if data.managers_id:
        await sync_cafe_managers(db, cafe, data.managers_id)

    await db.commit()
    await db.refresh(cafe)
    return cafe


async def update_cafe(
    db: AsyncSession,
    current_user: User,
    cafe_id: UUID,
    data: CafeUpdate,
) -> Optional[Cafe]:
    """Обновление объекта Кафе."""
    if current_user.role not in {
        UserRole.ADMIN,
        UserRole.MANAGER,
    }:
        raise PermissionError(
            'Недостаточно прав для обновления кафе.',
        )

    result = await db.execute(
        select(Cafe)
        .options(selectinload(Cafe.managers))
        .where(Cafe.id == cafe_id),
    )
    cafe = result.scalars().first()
    if not cafe:
        return None

    payload = data.model_dump(exclude_unset=True)

    for field in (
        'name',
        'address',
        'phone',
        'description',
        'photo_id',
        'active',
    ):
        if field in payload:
            value = payload[field]
            if field == 'phone' and value is not None:
                value = str(value)
            setattr(cafe, field, value)

    if 'managers_id' in payload:
        managers_ids = payload['managers_id'] or []
        await sync_cafe_managers(db, cafe, managers_ids)

    await db.commit()
    await db.refresh(cafe)
    return cafe
