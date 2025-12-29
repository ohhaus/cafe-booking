import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.cafe_scoped import get_cafe_or_none
from src.cafes.service import is_admin_or_manager, manager_can_cud_cafe
from src.common.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationErrorException,
)
from src.database.sessions import get_async_session
from src.tables.crud import table_crud
from src.tables.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.tables.schemas import (
    TableCreate,
    TableUpdate,
    TableWithCafeInfo,
)
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.get(
    '/{cafe_id}/tables',
    response_model=list[TableWithCafeInfo],
    response_model_by_alias=True,
    summary='Получение списка столов в кафе',
    description=(
        'Получение списка доступных для бронирования столов в кафе. '
        'Для администраторов и менеджеров - все столы '
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,
)
async def get_tables(
    cafe_id: UUID,
    show_all: bool = Query(
        False,
        title='Показывать все столы?',
        description='Показывать все столы в кафе или нет.',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> list[TableWithCafeInfo]:
    """Получение списка доступных для бронирования столов в кафе.

    Для администраторов и менеджеров - все столы (с возможностью выбора),
    для пользователей - только активные.
    """
    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        raise NotFoundException('Кафе не найдено.')

    privileged = is_admin_or_manager(current_user)
    include_all = show_all if privileged else False

    tables = await table_crud.list_tables(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        show_all=include_all,
    )
    return [TableWithCafeInfo.model_validate(t) for t in tables]


@router.post(
    '/{cafe_id}/tables',
    response_model=TableWithCafeInfo,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового стола в кафе',
    responses=CREATE_RESPONSES,
)
async def create_table(
    cafe_id: UUID,
    table_data: TableCreate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> TableWithCafeInfo:
    """Создает новый стол в кафе.

    Только для администраторов и менеджеров.
    """
    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        raise NotFoundException('Кафе не найдено.')

    if not await manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
    ):
        raise ForbiddenException(
            'Недостаточно прав для изменения этого кафе.',
        )

    try:
        table = await table_crud.create_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            data=table_data,
        )

        table = await table_crud.get_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            table_id=table.id,
        )
        if table is None:
            raise ValidationErrorException(
                'Не удалось получить созданный стол.',
            )

        return TableWithCafeInfo.model_validate(table)

    except ValueError as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных. Попробуйте позже.',
        ) from e


@router.get(
    '/{cafe_id}/tables/{table_id}',
    response_model=TableWithCafeInfo,
    response_model_by_alias=True,
    summary='Получение информации о столе по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def get_table_by_id(
    cafe_id: UUID,
    table_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> TableWithCafeInfo:
    """Получение информации о столе в кафе по его ID.

    Для администраторов и менеджеров - все столы,
    для пользователей - только активные.
    """
    table = await table_crud.get_table(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        table_id=table_id,
    )
    if not table:
        raise NotFoundException('Стол не найден.')
    return TableWithCafeInfo.model_validate(table)


@router.patch(
    '/{cafe_id}/tables/{table_id}',
    response_model=TableWithCafeInfo,
    response_model_by_alias=True,
    summary='Обновление информации о столе по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def update_table(
    cafe_id: UUID,
    table_id: UUID,
    table_data: TableUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> TableWithCafeInfo:
    """Обновление информации о столе в кафе по его ID.

    Только для администраторов и менеджеров.
    """
    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        raise NotFoundException('Кафе не найдено.')

    if not await manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
    ):
        raise ForbiddenException(
            'Недостаточно прав для изменения этого кафе.',
        )

    try:
        table = await table_crud.update_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            table_id=table_id,
            data=table_data,
        )
        if table is None:
            raise NotFoundException('Стол не найден.')

        return TableWithCafeInfo.model_validate(table)

    except ValueError as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных. Попробуйте позже.',
        ) from e
