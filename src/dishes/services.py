from src.database.service import DatabaseService
from src.dishes.models import Dish
from src.dishes.schemas import DishCreate, DishUpdate


class DishService(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Сервис для работы с блюдами."""

    def __init__(self) -> None:
        """Инициализирует сервис для модели Dish."""
        super().__init__(Dish)
