from fastapi import APIRouter

from src.media.views import router as media_router
from src.users.views import router as user_router

main_router = APIRouter()

main_router.include_router(user_router, prefix='/users')
main_router.include_router(media_router)
