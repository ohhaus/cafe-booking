# src/actions/responses.py
from typing import Any, Dict, Union

from src.actions.schemas import ActionInfo
from src.common.responses import (
    create_responses,
    list_responses,
    retrieve_responses,
)


ResponseType = Dict[Union[int, str], Dict[str, Any]]

GET_RESPONSES: ResponseType = list_responses()  # type: ignore
CREATE_RESPONSES: ResponseType = create_responses(ActionInfo)  # type: ignore
GET_BY_ID_RESPONSES: ResponseType = retrieve_responses()  # type: ignore
