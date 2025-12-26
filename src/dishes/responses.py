from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)
from src.dishes.schemas import DishInfo


GET_RESPONSES = list_responses()

CREATE_RESPONSES = create_responses(DishInfo)

GET_BY_ID_RESPONSES = retrieve_responses()
