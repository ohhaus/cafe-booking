import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.crud import cafe_crud
from src.cafes.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.cafes.schemas import CafeCreate, CafeInfo, CafeUpdate
from src.cafes.service import is_admin_or_manager, manager_can_cud_cafe
from src.common.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationErrorException,
)
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.post(
    '',
    response_model=CafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового кафе.',
    responses=CREATE_RESPONSES,
)
async def create_cafe(
    cafe_data: CafeCreate,
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.ADMIN],
        ),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Создает новое кафе. Только для администраторов."""
    try:
        cafe = await cafe_crud.create_cafe(db, cafe_data)
    except ValueError as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e
    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных при создании кафе',
        ) from e
    except DatabaseError as e:
        raise ValidationErrorException(
            'Ошибка базы данных',
        ) from e
    logger.info(
        'Кафе %s (%s) успешно создано',
        cafe.id,
        cafe.name,
        extra={
            'user_id': str(current_user.id),
            'cafe_id': str(cafe.id),
        },
    )
    return CafeInfo.model_validate(cafe)


@router.get(
    '',
    response_model=list[CafeInfo],
    summary=('Получение списка кафе.'),
    description=(
        'Получение списка кафе. Для администраторов и менеджеров - все кафе'
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,
)
async def get_all_cafes(
    show_all: bool = Query(
        False,
        title='Показывать все кафе?',
        description=(
            'Показывать все кафе или нет. По умолчанию показывает все кафе'
        ),
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> list[CafeInfo]:
    """Получение списка кафе.

    Для администраторов и менеджеров - все кафе (с возможностью выбора),
    для пользователей - только активные.
    """
    privileged = is_admin_or_manager(current_user)
    include_inactive = show_all if privileged else False

    cafes = await cafe_crud.get_list_cafe(
        db,
        include_inactive=include_inactive,
    )
    logger.info(
        'GET /cafes: найдено %d (include_inactive=%s, show_all=%s)',
        len(cafes),
        include_inactive,
        show_all,
        extra={'user_id': str(current_user.id)},
    )

    return [CafeInfo.model_validate(cafe) for cafe in cafes]


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Получение информации о кафе по его ID',
    responses=GET_BY_ID_RESPONSES,
)
async def get_cafe_by_id(
    cafe_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Получение информации о кафе по его ID.

    Для администраторов и менеджеров - все кафе,
    для пользователей - только активные.
    """
    include_inactive = is_admin_or_manager(current_user)

    cafe = await cafe_crud.get_cafe_by_id(
        db,
        cafe_id=cafe_id,
        include_inactive=include_inactive,
    )
    if not cafe:
        raise NotFoundException('Кафе не найдено')

    return CafeInfo.model_validate(cafe)


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Обновление информации о кафе по его ID',
    responses=GET_BY_ID_RESPONSES,
)
async def update_cafe(
    cafe_id: UUID,
    cafe_data: CafeUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Обновление информации о кафе по его ID.

    Только для администраторов и менеджеров.
    """
    cafe = await cafe_crud.get_cafe_by_id(
        db,
        cafe_id=cafe_id,
        include_inactive=True,
    )
    if cafe is None:
        raise NotFoundException('Кафе не найдено')

    if not await manager_can_cud_cafe(
        db,
        user=current_user,
        cafe_id=cafe_id,
    ):
        raise ForbiddenException(
            'Недостаточно прав для изменения этого кафе',
        )

    try:
        cafe = await cafe_crud.update_cafe(db, cafe, cafe_data)

    except ValueError as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except IntegrityError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Конфликт данных при обновлении кафе',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        raise ValidationErrorException(
            'Ошибка базы данных при обновлении кафе',
        ) from e

    logger.info(
        'Кафе %s обновлено пользователем %s',
        cafe.id,
        current_user.id,
        extra={'user_id': str(current_user.id), 'cafe_id': str(cafe.id)},
    )
    return CafeInfo.model_validate(cafe)
