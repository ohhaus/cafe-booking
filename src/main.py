from fastapi import FastAPI

from api import main_router


app = FastAPI(title='Cafe Booking')

app.include_router(main_router)
