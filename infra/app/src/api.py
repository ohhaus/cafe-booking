from fastapi import APIRouter

from src.auth.views import router as auth_router
from src.booking.views import router as booking_router
from src.cafes.views import router as cafes_router
from src.dishes.views import router as dishes_router
from src.media.views import router as media_router
from src.slots.views import router as slots_router
from src.tables.views import router as table_router
from src.users.views import router as user_router


main_router = APIRouter()

main_router.include_router(
    auth_router,
    prefix='/auth',
    tags=['Aутентификация'],
)
main_router.include_router(user_router, prefix='/users', tags=['Пользователи'])
main_router.include_router(cafes_router, prefix='/cafes', tags=['Кафе'])
main_router.include_router(table_router, prefix='/cafes', tags=['Столы'])
main_router.include_router(
    slots_router,
    prefix='/cafes',
    tags=['Временные слоты'],
)
main_router.include_router(dishes_router, prefix='/dishes', tags=['Блюда'])
main_router.include_router(
    booking_router,
    prefix='/booking',
    tags=['Бронирования'],
)
main_router.include_router(media_router, prefix='/media', tags=['Изображения'])
