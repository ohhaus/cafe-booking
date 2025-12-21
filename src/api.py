from fastapi import APIRouter

from src.booking.views import router as booking_router
from src.cafes.views import router as cafe_router
from src.slots.views import router as slot_router
from src.tables.views import router as table_router
from src.users.views import router as user_router


main_router = APIRouter()

main_router.include_router(user_router, prefix='/users')
main_router.include_router(cafe_router, prefix='/cafe')
main_router.include_router(slot_router, prefix='/cafe')
main_router.include_router(table_router, prefix='/cafe')
main_router.include_router(booking_router)
