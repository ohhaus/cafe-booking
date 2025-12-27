from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api import main_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управляет жизненным циклом FastAPI-приложения."""
    yield


app = FastAPI(title='Cafe Booking', lifespan=lifespan)

app.include_router(main_router)
