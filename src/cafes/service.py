import logging
from uuid import UUID

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.cafes.models import Cafe, cafes_managers
from src.users.models import User, UserRole


logger = logging.getLogger('app')


def is_admin_or_manager(user: User) -> bool:
    """Проверка на менеджера и админа."""
    return user.role in (UserRole.ADMIN, UserRole.MANAGER)


def manager_conditions(
    ids: set[UUID],
) -> tuple[ColumnElement[bool], ...]:
    """Возвращает кортеж условий для запроса."""
    return (
        User.id.in_(ids),
        User.role.in_((UserRole.ADMIN, UserRole.MANAGER)),
        User.active.is_(True),
    )


async def manager_can_cud_cafe(
    db: AsyncSession,
    *,
    user: User,
    cafe_id: UUID,
) -> bool:
    """Ограничение CUD (Create, Update, Delete) для MANAGER.

    Позволяет проводить опасные операции CUD только с теми кафе
    с которыми он связан, в том числе слоты и столы.
    """
    if user.role != UserRole.MANAGER:
        return True

    stmt = select(
        exists().where(
            cafes_managers.columns.cafe_id == cafe_id,
            cafes_managers.columns.user_id == user.id,
        ),
    )

    return bool(await db.scalar(stmt))


async def sync_cafe_managers(
    db: AsyncSession,
    cafe: Cafe,
    new_managers_ids: list[UUID],
) -> None:
    """Синхронизирует список менеджеров и админов кафе.

    Переданным списком UUID.
    """
    new_ids = set(new_managers_ids)

    if new_ids:
        conds = manager_conditions(new_ids)

        result = await db.execute(
            select(func.count(User.id)).where(*conds),
        )
        cnt = int(result.scalar() or 0)

        if cnt != len(new_ids):
            result = await db.execute(
                select(User.id).where(*conds),
            )
            valid_ids = set(result.scalars().all())
            missing = new_ids - valid_ids
            logger.warning(
                'Invalid managers ids for cafe %s: missing=%s',
                cafe.id,
                missing,
            )
            raise ValueError(
                'Некоторые managers_id не найдены'
                'или не являются активными ADMIN/MANAGER: '
                f'{missing}',
            )

    del_stmt = delete(cafes_managers).where(
        cafes_managers.columns.cafe_id == cafe.id,
    )
    if new_ids:
        del_stmt = del_stmt.where(
            cafes_managers.columns.user_id.notin_(new_ids),
        )
    await db.execute(del_stmt)

    if new_ids:
        ins_stmt = (
            pg_insert(cafes_managers)
            .values([{'cafe_id': cafe.id, 'user_id': mid} for mid in new_ids])
            .on_conflict_do_nothing(index_elements=['cafe_id', 'user_id'])
        )
        await db.execute(ins_stmt)
