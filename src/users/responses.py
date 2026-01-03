from src.common.responses import (
    retrieve_responses,
    user_create_response,
    user_list_responses,
    user_me_patch_responses,
    user_retrieve_responses,
)
from src.users.schemas import UserRead


USER_LIST_RESPONSES = user_list_responses()

USER_CREATE_RESPONSES = user_create_response(UserRead)

USER_RETRIEVE_RESPONSES = user_retrieve_responses()

USER_ME_PATCH_RESPONSES = user_me_patch_responses()

USER_UPDATE_RESPONSES = retrieve_responses()
