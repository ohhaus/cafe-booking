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
from src.slots.crud import slot_crud
from src.slots.responses import (
    CREATE_RESPONSES,
    GET_BY_ID_RESPONSES,
    GET_RESPONSES,
)
from src.slots.schemas import (
    TimeSlotCreate,
    TimeSlotUpdate,
    TimeSlotWithCafeInfo,
)
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()

logger = logging.getLogger('app')


@router.get(
    '/{cafe_id}/time_slots',
    response_model=list[TimeSlotWithCafeInfo],
    summary='Получение списка временных слотов в кафе',
    description=(
        'Получение списка доступных для бронирования временных слотов в кафе. '
        'Для администраторов и менеджеров - все слоты '
        '(с возможностью выбора), для пользователей - только активные.'
    ),
    responses=GET_RESPONSES,
)
async def get_time_slots(
    cafe_id: UUID,
    show_all: bool = Query(
        False,
        title='Показывать все временные слоты?',
        description='Показывать все временные слоты в кафе или нет.',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> list[TimeSlotWithCafeInfo]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Для администраторов и менеджеров - все слоты (с возможностью выбора),
    для пользователей - только активные.
    """
    cafe = await get_cafe_or_none(db, cafe_id)
    if not cafe:
        raise NotFoundException('Кафе не найдено.')

    privileged = is_admin_or_manager(current_user)
    include_all = show_all if privileged else False

    slots = await slot_crud.list_slots(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        show_all=include_all,
    )

    return [TimeSlotWithCafeInfo.model_validate(slot) for slot in slots]


@router.post(
    '/{cafe_id}/time_slots',
    response_model=TimeSlotWithCafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового временного слота в кафе',
    responses=CREATE_RESPONSES,
)
async def create_time_slot(
    cafe_id: UUID,
    slot_data: TimeSlotCreate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> TimeSlotWithCafeInfo:
    """Создает нового временного слота в кафе.

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

    slot = await slot_crud.create_slot(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        data=slot_data,
    )

    try:
        slot = await slot_crud.create_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            data=slot_data,
        )
        if slot is None:
            raise ValidationErrorException('Не удалось создать слот.')

        return TimeSlotWithCafeInfo.model_validate(slot)

    except (ValueError,) as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except (PermissionError,) as e:
        await db.rollback()
        raise ForbiddenException(str(e)) from e

    except (LookupError,) as e:
        await db.rollback()
        raise NotFoundException(str(e)) from e

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
    '/{cafe_id}/time_slots/{slot_id}',
    response_model=TimeSlotWithCafeInfo,
    summary='Получение информации о временном слоте по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def get_time_slot_by_id(
    cafe_id: UUID,
    slot_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    db: AsyncSession = Depends(get_async_session),
) -> TimeSlotWithCafeInfo:
    """Получение информации о временном слоте в кафе по его ID.

    Для администраторов и менеджеров - видят активные и не активные слоты,
    для пользователей - только активные.
    """
    slot = await slot_crud.get_slot(
        db,
        current_user=current_user,
        cafe_id=cafe_id,
        slot_id=slot_id,
    )
    if not slot:
        raise NotFoundException('Слот не найден.')

    return TimeSlotWithCafeInfo.model_validate(slot)


@router.patch(
    '/{cafe_id}/time_slots/{slot_id}',
    response_model=TimeSlotWithCafeInfo,
    summary='Обновление информации о временном слоте по ID',
    responses=GET_BY_ID_RESPONSES,
)
async def update_time_slot(
    cafe_id: UUID,
    slot_id: UUID,
    slot_data: TimeSlotUpdate,
    current_user: User = Depends(
        require_roles(allowed_roles=[UserRole.MANAGER, UserRole.ADMIN]),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> TimeSlotWithCafeInfo:
    """Обновление информации о временом слоте в кафе по его ID.

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
        raise ForbiddenException('Недостаточно прав для изменения этого кафе.')

    try:
        slot = await slot_crud.update_slot(
            db,
            current_user=current_user,
            cafe_id=cafe_id,
            slot_id=slot_id,
            data=slot_data,
        )
        if slot is None:
            raise NotFoundException('Слот не найден.')
        return TimeSlotWithCafeInfo.model_validate(slot)

    except (ValueError,) as e:
        await db.rollback()
        raise ValidationErrorException(str(e)) from e

    except (PermissionError,) as e:
        await db.rollback()
        raise ForbiddenException(str(e)) from e

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
