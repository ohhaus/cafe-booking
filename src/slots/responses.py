from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)
from src.slots.schemas import TimeSlotInfo


GET_RESPONSES = list_responses()

CREATE_RESPONSES = create_responses(TimeSlotInfo)

GET_BY_ID_RESPONSES = retrieve_responses()
