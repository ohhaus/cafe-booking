# src/dishes/services.py

from src.database.service import DatabaseService
from src.dishes.models import Dish
from src.dishes.schemas import DishCreate, DishUpdate


class DishService(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Сервис для работы с блюдами."""


dish_service = DishService(Dish)
