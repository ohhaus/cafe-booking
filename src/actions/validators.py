from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.models import Action
from src.cafes.models import Cafe
from src.common.exceptions import BadRequestException, NotFoundException


async def check_exists_action(
    action_id: UUID,
    session: AsyncSession,
) -> Action:
    """Проверка существования акции по ID.

    Args:
        action_id: UUID акции
        session: Сессия БД

    Returns:
        Объект Action

    Raises:
        NotFoundException: Если акция не найдена

    """
    result = await session.execute(
        select(Action).where(Action.id == action_id),
    )
    action = result.scalars().first()

    if not action:
        raise NotFoundException(
            detail=f'Акция с ID {action_id} не найдена',
        )

    return action


async def check_exists_cafes_ids(
    cafes_ids: list[UUID],
    session: AsyncSession,
) -> list[Cafe]:
    """Проверяет, что все кафе из списка существуют и активны.

    Args:
        cafes_ids: Список UUID кафе
        session: Сессия БД

    Returns:
        Список объектов Cafe

    Raises:
        BadRequestException: Если список пуст
        NotFoundException: Если не все кафе существуют

    """
    # Проверка на пустой список
    if not cafes_ids:
        raise BadRequestException(
            message='Список ID кафе не может быть пустым',
        )

    # Получаем все существующие и активные кафе
    result = await session.execute(
        select(Cafe).where(
            Cafe.id.in_(cafes_ids),
            Cafe.active.is_(True),
        ),
    )
    existing_cafes = list(result.scalars().all())
    existing_ids = {cafe.id for cafe in existing_cafes}

    # Проверяем, что все запрошенные кафе найдены
    missing = set(cafes_ids) - existing_ids
    if missing:
        raise NotFoundException(
            message=f'Кафе с ID {missing} не найдены или неактивны',
        )

    return existing_cafes


async def check_action_name_unique(
    name: str,
    session: AsyncSession,
    exclude_id: UUID | None = None,
) -> None:
    """Проверяет уникальность названия акции.

    Args:
        name: Название акции для проверки
        session: Сессия БД
        exclude_id: ID акции, которую исключаем из проверки (для обновления)

    Raises:
        BadRequestException: Если название уже существует

    """
    query = select(Action).where(Action.name == name)

    if exclude_id:
        query = query.where(Action.id != exclude_id)

    result = await session.execute(query)
    existing_action = result.scalars().first()

    if existing_action:
        raise BadRequestException(
            message=f"Акция с названием '{name}' уже существует",
        )
