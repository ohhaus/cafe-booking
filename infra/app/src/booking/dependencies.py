from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.booking.services import BookingService
from src.cache.client import RedisCache, get_cache
from src.database import get_async_session


async def get_booking_service(
    session: AsyncSession = Depends(get_async_session),
    cache: RedisCache = Depends(get_cache),
) -> BookingService:
    """Возвращает экземпляр BookingService с внедрёнными зависимостями."""
    return BookingService(session=session, cache=cache)
