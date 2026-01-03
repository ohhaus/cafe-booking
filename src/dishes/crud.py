from typing import Tuple
from uuid import UUID

from src.database.service import DatabaseService
from src.dishes.models import Dish
from src.dishes.schemas import DishCreate, DishUpdate


Pair = Tuple[UUID, UUID]


class DishesCRUD(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Слой доступа к данным для бронирований."""

    pass


dishes_crud = DishesCRUD(Dish)
