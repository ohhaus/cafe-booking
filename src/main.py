from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api import main_router
from src.common.exception_handlers import add_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управляет жизненным циклом FastAPI-приложения."""
    yield


app = FastAPI(title='Cafe Booking', lifespan=lifespan)
add_exception_handlers(app)

app.include_router(main_router)
