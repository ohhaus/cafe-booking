from src.cafes.schemas import CafeInfo
from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)


GET_RESPONSES = list_responses()

CREATE_RESPONSES = create_responses(CafeInfo)

GET_BY_ID_RESPONSES = retrieve_responses()
