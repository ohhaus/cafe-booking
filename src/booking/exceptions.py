import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import DatabaseError, IntegrityError


logger = logging.getLogger('app')


def handle_booking_exceptions(
    e: Exception,
    user_id: UUID,
    action: str,
) -> None:
    """Централизованная обработка исключений для операций с бронированием.

    Args:
        e: Возникшее исключение.
        user_id: ID пользователя для логирования.
        action: Действие (например, 'создании', 'обновлении').

    """
    if isinstance(e, IntegrityError):
        logger.error(
            'Ошибка целостности данных при %s брони: %s',
            action,
            str(e),
            extra={'user_id': str(user_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Конфликт данных: возможно, дублирующая бронь или '
            'нарушение ограничений.',
        ) from e

    if isinstance(e, DatabaseError):
        logger.error(
            'Ошибка базы данных при %s брони: %s',
            action,
            str(e),
            extra={'user_id': str(user_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Временная ошибка базы данных. Попробуйте позже.',
        ) from e

    logger.critical(
        'Неожиданная ошибка при %s брони: %s',
        action,
        str(e),
        extra={'user_id': str(user_id)},
        exc_info=True,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail='Внутренняя ошибка сервера.',
    ) from e
