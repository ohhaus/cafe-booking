from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings


@pytest_asyncio.fixture(scope='session')
async def engine():  # noqa
    engine = create_async_engine(
        settings.database.URL,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:  # noqa
    async_session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with engine.connect() as conn:
        trans = await conn.begin()

        async with async_session_factory(bind=conn) as session:
            yield session

        await trans.rollback()
