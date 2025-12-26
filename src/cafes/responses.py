from http import HTTPStatus

from src.cafes.schemas import CafeInfo
from src.common.errors import (
    ERROR_400,
    ERROR_401,
    ERROR_403,
    ERROR_404,
    ERROR_422,
)
from src.common.responses import OK_RESPONSES, success_response


CREATED_RESPONSE = success_response(
    HTTPStatus.CREATED,
    CafeInfo,
)


GET_RESPONSES = {
    **OK_RESPONSES,
    **ERROR_401,
    **ERROR_422,
}

CREATE_RESPONSES = {
    **CREATED_RESPONSE,
    **ERROR_400,
    **ERROR_401,
    **ERROR_403,
    **ERROR_422,
}

GET_BY_ID_RESPONSES = {
    **CREATED_RESPONSE,
    **ERROR_400,
    **ERROR_401,
    **ERROR_403,
    **ERROR_404,
    **ERROR_422,
}
