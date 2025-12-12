from enum import IntEnum


class BookingStatus(IntEnum):
    """Статус бронирования."""
    СОЗДАНО = 0
    АКТИВНО = 1
    ЗАВЕРШЕНО = 2

    # Псевдонимы на английском для удобства использования в коде
    CREATED = СОЗДАНО
    ACTIVE = АКТИВНО
    COMPLETED = ЗАВЕРШЕНО