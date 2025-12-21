from fastapi import APIRouter

from src.auth import auth_router
from src.booking.views import router as booking_router
from src.dishes import dishes_router
from src.media import media_router
from src.users import user_router


main_router = APIRouter()

main_router.include_router(
    auth_router,
    prefix='/auth',
    tags=['Aутентификация'],
)
main_router.include_router(user_router, prefix='/users', tags=['Пользователи'])
main_router.include_router(media_router, prefix='/media', tags=['Изображения'])
main_router.include_router(
    booking_router,
    prefix='/booking',
    tags=['Бронирования'],
)
main_router.include_router(dishes_router, prefix='/dishes', tags=['Блюда'])
