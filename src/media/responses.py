from src.common.responses import (
    media_get_by_id_responses,
    media_post_responses,
)
from src.media.schemas import MediaInfo


CREATE_RESPONSES = media_post_responses(MediaInfo)

GET_BY_ID_RESPONSES = media_get_by_id_responses()
