from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings


def create_db_engine(connection_string: str) -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy."""
    return create_async_engine(
        connection_string,
        pool_timeout=settings.database.POOL_TIMEOUT,
        pool_recycle=settings.database.POOL_RECYCLE,
        pool_size=settings.database.POOL_SIZE,
        max_overflow=settings.database.MAX_OVERFLOW,
        pool_pre_ping=settings.database.POOL_PING,
        echo=settings.database.ECHO_SQL,
    )


engine = create_db_engine(settings.database.URL)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор асинхронных сессий."""
    async with AsyncSessionLocal() as async_session:
        try:
            yield async_session
        except Exception:
            await async_session.rollback()
            raise
        finally:
            await async_session.close()
