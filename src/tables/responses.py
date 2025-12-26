from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)
from src.tables.schemas import TableInfo


GET_RESPONSES = list_responses()

CREATE_RESPONSES = create_responses(TableInfo)

GET_BY_ID_RESPONSES = retrieve_responses()
