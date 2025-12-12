from enum import IntEnum


MAX_NOTES_LENGTH = 255

class BookingStatus(IntEnum):
    """Статус бронирования"""
    CREATED = 0
    ACTIVE = 1
    COMPLETED = 2
    CANCELED = 3
