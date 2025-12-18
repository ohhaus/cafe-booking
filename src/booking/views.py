import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    summary='Создать бронирование',
    description='Создать новое бронирование для указанного кафе и даты.',
    responses={
        200: {'description': 'Успешно'},
        400: {'description': 'Ошибка в параметрах запроса'},
        401: {'description': 'Неавторизированный пользователь'},
        422: {'description': 'Ошибка валидации данных'},
    },
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
        extra={'user_id': str(current_user.id)},
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
            extra={'user_id': str(current_user.id)},
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
            extra={'user_id': str(current_user.id)},
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
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except HTTPException as e:
        logger.warning(
            'HTTP ошибка при создании брони: %s',
            e.detail,
            extra={'user_id': str(current_user.id)},
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.critical(
            'Неожиданная ошибка при создании брони: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


@router.get(
    '/',
    response_model=List[BookingInfo],
    summary='Получение списка бронирований',
    description=(
        'Получение списка бронирований. '
        'Для администраторов и менеджеров - все бронирования '
        '(с возможностью выбора), '
        'для пользователей - только свои (параметры игнорируются, '
        'кроме ID кафе).'
    ),
    responses={
        200: {'description': 'Успешно'},
        401: {'description': 'Неавторизированный пользователь'},
        422: {'description': 'Ошибка валидации данных'},
    },
)
async def get_all_bookings(
    show_all: bool = Query(
        False,
        title='Показывать все бронирования?',
        description='Показывать все бронирования или нет. По умолчанию '
        'показывает только активные.',
    ),
    cafe_id: Optional[UUID] = Query(
        None,
        title='Cafe Id',
        description='ID кафе, в котором показывать бронирования. Если не '
        'задано - показывает бронирования во всех кафе.',
    ),
    user_id: Optional[UUID] = Query(
        None,
        title='User Id',
        description='ID пользователя, бронирования которого показывать. Если '
        'не задано - показывает бронирования всех пользователей. '
        '(только для staff)',
    ),
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> List[BookingInfo]:
    """Обработчик GET /booking для получения списка бронирований."""
    try:
        crud = BookingCRUD(session)
        is_staff = current_user.is_staff()

        bookings = await crud.get_bookings(
            current_user_id=current_user.id,
            is_staff=is_staff,
            show_all=(show_all if is_staff else False),
            cafe_id=cafe_id,
            user_id=(user_id if is_staff else None),
        )

        logger.info(
            'Найдено %d бронирований для пользователя %s',
            len(bookings),
            current_user.id,
            extra={'user_id': str(current_user.id)},
        )

        return [BookingInfo.model_validate(b) for b in bookings]

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении бронирований: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении бронирований: %s',
            str(e),
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e


@router.get(
    '/{booking_id}',
    response_model=BookingInfo,
    summary='Получение информации о бронировании по ID',
    description='Получение полной информации о бронировании по его уникальному'
    ' идентификатору. Пользователь может просматривать только свои'
    ' бронирования, менеджеры и администраторы — любые.',
    responses={
        200: {'description': 'Успешно'},
        401: {'description': 'Неавторизированный пользователь'},
        403: {'description': 'Доступ запрещён'},
        404: {'description': 'Бронирование не найдено'},
        422: {'description': 'Некорректный формат ID'},
    },
)
async def get_booking_by_id(
    booking_id: UUID,
    current_user: User = Depends(require_roles(allow_guest=False)),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Получить бронирование по ID с учётом прав доступа.

    Args:
        booking_id (UUID): ID бронирования.
        current_user (User): Текущий авторизованный пользователь.
        session (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        BookingInfo: Данные бронирования.

    Raises:
        HTTPException: 404 если бронирование не найдено или недоступно.

    """
    try:
        logger.info(
            'Пользователь %s запрашивает бронирование %s',
            current_user.id,
            booking_id,
            extra={'user_id': current_user.id},
        )

        crud = BookingCRUD(session)
        booking = await crud.get_booking_by_id(
            booking_id,
            current_user_id=current_user.id,
            is_staff=current_user.is_staff(),
        )

        if not booking:
            logger.warning(
                'Бронирование %s не найдено',
                booking_id,
                extra={'user_id': current_user.id},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено.',
            )

        return BookingInfo.model_validate(booking)

    except HTTPException:
        raise

    except DatabaseError as e:
        logger.error(
            'Ошибка базы данных при получении бронирования: %s',
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    except Exception as e:
        logger.critical(
            'Неожиданная ошибка при получении бронирования: %s',
            str(e),
            extra={
                'user_id': str(current_user.id),
                'booking_id': str(booking_id),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера.',
        ) from e
