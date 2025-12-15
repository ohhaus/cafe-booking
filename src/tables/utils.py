from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.users.models import User, UserRole


def is_admin_or_manager(
    user: User,
) -> bool:
    """Проверка на админа или менеджера."""
    return user.role in {UserRole.ADMIN, UserRole.MANAGER}


async def get_cafe_or_none(
    db: AsyncSession,
    cafe_id: UUID,
) -> Optional[Cafe]:
    """Запрос к БД на получение кафе по UUID."""
    result = await db.execute(select(Cafe).where(Cafe.id == cafe_id))
    return result.scalars().first()
