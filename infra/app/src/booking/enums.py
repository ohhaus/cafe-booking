from enum import IntEnum


class BookingStatus(IntEnum):
    """Статус бронирования."""

    BOOKING = 0  # Забронировано
    CANCELED = 1  # Отменено
    ACTIVE = 2  # Активно
    COMPLETED = 3  # Завершено
