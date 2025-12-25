from src.common.responses import (
                      CREATED_RESPONSE,
                      ERROR_400_RESPONSE,
                      ERROR_401_RESPONSE,
                      ERROR_403_RESPONSE,
                      ERROR_404_RESPONSE,
                      ERROR_422_RESPONSE,
                      OK_RESPONSES,
)


# --- Ответы для Блюд ---
DISH_GET_RESPONSES = {**OK_RESPONSES,
                      **ERROR_401_RESPONSE,
                      **ERROR_422_RESPONSE}

DISH_CREATE_RESPONSES = {**CREATED_RESPONSE,
                         **ERROR_400_RESPONSE,
                         **ERROR_401_RESPONSE,
                         **ERROR_403_RESPONSE,
                         **ERROR_422_RESPONSE}

DISH_GET_BY_ID_RESPONSES = {**CREATED_RESPONSE,
                            **ERROR_400_RESPONSE,
                            **ERROR_401_RESPONSE,
                            **ERROR_403_RESPONSE,
                            **ERROR_404_RESPONSE,
                            **ERROR_422_RESPONSE}
