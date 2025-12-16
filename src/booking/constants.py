from enum import IntEnum

MAX_NOTES_LENGTH = 255
MAX_BOOKING_DATE = 365  # 1 год
MAX_GUEST_NUMBER = 100


class BookingStatus(IntEnum):
    """Статус бронирования."""

    BOOKING = 0  # Забронировано
    CANCELED = 1  # Отменено
    ACTIVE = 2  # Активно
    COMPLETED = 3  # Завершено
