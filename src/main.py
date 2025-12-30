from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api import main_router
from src.cache.client import cache


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управляет жизненным циклом FastAPI-приложения."""
    await cache.connect()
    yield
    await cache.close()


app = FastAPI(title='Cafe Booking', lifespan=lifespan)

app.include_router(main_router)
