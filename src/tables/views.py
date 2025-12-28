import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.cafe_scoped import get_cafe_or_none
from src.cafes.service import is_admin_or_manager
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
    try:
        cafe = await get_cafe_or_none(db, cafe_id)
        if not cafe:
            logger.warning(
                'Кафе %s не найдено при получении списка столов',
                cafe_id,
                extra={
                    'user_id': str(current_user.id),
                    'cafe_id': str(cafe_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Кафе не найдено.',
            )

        privileged = is_admin_or_manager(current_user)
        include_all = show_all if privileged else False

        tables = await table_crud.list_tables(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            show_all=include_all,
        )

        return [TableWithCafeInfo.model_validate(table) for table in tables]

    except asyncio.CancelledError:
        raise

    except HTTPException:
        raise

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при получении списка столов (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при получении списка столов (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Не удалось получить созданный стол.',
            )

        logger.info(
            'Стол %s успешно создан пользователем %s (cafe=%s)',
            table.id,
            current_user.id,
            cafe_id,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table.id),
            },
        )
        return TableWithCafeInfo.model_validate(table)

    except asyncio.CancelledError:
        raise

    except ValueError as e:
        await db.rollback()
        logger.warning(
            'Ошибка валидации при создании стола (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except PermissionError as e:
        await db.rollback()
        logger.warning(
            'Доступ запрещен при создании стола (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    except LookupError as e:
        await db.rollback()
        logger.warning(
            'Кафе не найдено при создании стола (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'Ошибка целостности данных при создании стола (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при создании стола (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except HTTPException as e:
        logger.warning(
            'HTTP ошибка при создании стола (cafe=%s): %s',
            cafe_id,
            e.detail,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при создании стола (cafe=%s): %s',
            cafe_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
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
    try:
        table = await table_crud.get_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            table_id=table_id,
        )
        if not table:
            logger.warning(
                'Стол %s не найден (cafe=%s)',
                table_id,
                cafe_id,
                extra={
                    'user_id': str(current_user.id),
                    'cafe_id': str(cafe_id),
                    'table_id': str(table_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Стол не найден.',
            )

        return TableWithCafeInfo.model_validate(table)

    except asyncio.CancelledError:
        raise

    except HTTPException:
        raise

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при получении стола (cafe=%s, table=%s): %s',
            cafe_id,
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при получении стола (cafe=%s, table=%s): %s',
            cafe_id,
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


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
    try:
        table = await table_crud.update_table(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            table_id=table_id,
            data=table_data,
        )
        if table is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Стол не найден.',
            )

        logger.info(
            'Стол %s успешно обновлён пользователем %s (cafe=%s)',
            table.id,
            current_user.id,
            cafe_id,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table.id),
            },
        )

        return TableWithCafeInfo.model_validate(table)

    except asyncio.CancelledError:
        raise

    except ValueError as e:
        await db.rollback()
        logger.error(
            'PATCH table %s ValueError: %s',
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except PermissionError as e:
        await db.rollback()
        logger.warning(
            'PATCH table %s Forbidden: %s',
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    except HTTPException as e:
        logger.warning(
            'PATCH table %s HTTPException: %s',
            table_id,
            e.detail,
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
        )
        raise

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'PATCH table %s IntegrityError: %s',
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных или нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'PATCH table %s DatabaseError: %s',
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        await db.rollback()
        logger.critical(
            'PATCH table %s Unexpected error: %s',
            table_id,
            str(e),
            extra={
                'user_id': str(current_user.id),
                'cafe_id': str(cafe_id),
                'table_id': str(table_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e
