from src.booking import Booking
from src.booking.crud import BookingCRUD
from src.booking.schemas import BookingCreate
from src.users.models import User


async def create_or_update_booking(
    booking_data: BookingCreate,
    current_user: User,
    crud: BookingCRUD,
) -> Booking:
    """Создаёт бронирование и связанные с ним пары стол-слот."""
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
    return booking
