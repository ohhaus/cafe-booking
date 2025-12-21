from fastapi import APIRouter

from src.booking.views import router as booking_router
from src.cafes.view import router as cafe_router
from src.users.views import router as user_router


main_router = APIRouter()

main_router.include_router(user_router, prefix='/users')
main_router.include_router(cafe_router)
main_router.include_router(booking_router)
