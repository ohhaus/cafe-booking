from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe, cafes_managers
from src.users.models import User, UserRole


async def sync_cafe_managers(
    db: AsyncSession,
    cafe: Cafe,
    new_managers_ids: list[UUID],
) -> None:
    """Синхронизирует список менеджеров кафе с переданным списком UUID."""
    new_ids = set(new_managers_ids)

    result = await db.execute(
        select(cafes_managers.c.user_id).where(
            cafes_managers.c.cafe_id == cafe.id,
        ),
    )
    current_ids = set(result.scalars().all())

    to_add = new_ids - current_ids
    to_remove = current_ids - new_ids

    if new_ids:
        result = await db.execute(
            select(User.id).where(
                User.id.in_(new_ids),
                User.role == UserRole.MANAGER,
                User.active.is_(True),
            ),
        )
        valid_ids = set(result.scalars().all())

        if valid_ids != new_ids:
            missing = new_ids - valid_ids
            raise ValueError(
                'Некоторые managers_id не найдены или'
                f'не являются активными MANAGER: {missing}',
            )

    if to_remove:
        await db.execute(
            delete(cafes_managers).where(
                cafes_managers.c.cafe_id == cafe.id,
                cafes_managers.c.user_id.in_(to_remove),
            ),
        )
    if to_add:
        await db.execute(
            insert(cafes_managers),
            [
                {'cafe_id': cafe.id, 'user_id': manager_id}
                for manager_id in to_add
            ],
        )
