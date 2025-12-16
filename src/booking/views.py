import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.crud import BookingCRUD
from src.booking.schemas import BookingCreate, BookingInfo
from src.booking.validators import validate_booking_data
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter(
    prefix='/booking',
    tags=['Бронирования'],
)

logger = logging.getLogger('app')


@router.post(
    '/',
    response_model=BookingInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    booking_data: BookingCreate,
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.USER, UserRole.MANAGER, UserRole.ADMIN],
        ),
    ),
    db: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Создаёт новое бронирование.

    Args:
        booking_data (BookingCreate): Данные для создания брони.
        current_user (User): Текущий авторизованный пользователь.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        BookingInfo: Созданная бронь с подробной информацией.

    """
    logger.info(
        'Пользователь %s инициировал создание бронирования на дату %s',
        current_user.id,
        booking_data.booking_date,
        extra={'user_id': current_user.id},
    )

    try:
        crud = BookingCRUD(db)
        await validate_booking_data(crud, booking_data, current_user)

        # Создание брони
        booking = await crud.create_booking(
            user_id=current_user.id,
            cafe_id=booking_data.cafe_id,
            guest_number=booking_data.guest_number,
            note=booking_data.note,
            status=booking_data.status,
            booking_date=booking_data.booking_date,
        )

        # Создание связей стол-слот
        for ts in booking_data.tables_slots:
            await crud.create_booking_slot(
                booking_id=booking.id,
                table_id=ts.table_id,
                slot_id=ts.slot_id,
                booking_date=booking_data.booking_date,
            )

        await db.commit()
        logger.info(
            'Бронирование %s успешно создано',
            booking.id,
            extra={'user_id': current_user.id},
        )

        await db.refresh(
            booking,
            attribute_names=['booking_table_slots', 'user', 'cafe'],
        )

        return BookingInfo.model_validate(booking)

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            'Ошибка целостности данных при создании брони: %s',
            str(e),
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных: возможно, дублирующая бронь или '
            'нарушение ограничений.',
        ) from e

    except DatabaseError as e:
        await db.rollback()
        logger.error(
            'Ошибка базы данных при создании брони: %s',
            str(e),
            extra={'user_id': current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except HTTPException as e:
        logger.warning(
            'HTTP ошибка при создании брони: %s',
            e.detail,
            extra={'user_id': current_user.id},
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при создании брони: %s',
            str(e),
            extra={'user_id': current_user.id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e
