from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api import main_router
from src.cache.client import cache
from src.common.exception_handlers import add_exception_handlers
from src.common.super_user import create_superuser


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управляет жизненным циклом FastAPI-приложения."""
    await cache.connect()
    await create_superuser()
    yield
    await cache.close()


app = FastAPI(title='Cafe Booking', lifespan=lifespan)

add_exception_handlers(app)


@app.get('/health', include_in_schema=False)
async def health_check() -> JSONResponse:
    """Health check endpoint для Docker health checks."""
    return JSONResponse(
        status_code=200,
        content={'status': 'healthy', 'service': 'cafe-booking'},
    )


app.include_router(main_router)
