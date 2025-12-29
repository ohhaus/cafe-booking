# src/main.py

from fastapi import FastAPI

from src.api import main_router
from src.common.exception_handlers import add_exception_handlers


app = FastAPI(title='Cafe Booking')
add_exception_handlers(app)

app.include_router(main_router)
