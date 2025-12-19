import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DISH_MAX_PRICE = 10000
DISH_MIN_PRICE = 1
MAX_NAME_LENGTH = 100
MAX_ADDRESS_LENGTH = 250
MAX_PHONE_LENGTH = 32
MAX_DESCRIPTION_LENGTH = 500
MIN_DESCRIPTION_LENGTH = 1
UUID_LENGTH = 36


class DatabaseSettings(BaseSettings):
    """Настройки базы данных."""

    URL: str = Field(
        default='postgresql+asyncpg://postgres:postgres@localhost:5432/postgres',  # noqa: E501
    )
    POOL_TIMEOUT: int = Field(default=30)
    POOL_RECYCLE: int = Field(default=1800)
    POOL_SIZE: int = Field(default=20)
    MAX_OVERFLOW: int = Field(default=30)
    POOL_PING: bool = Field(default=True)
    ECHO_SQL: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix='DATABASE_',
        env_file='.env',
        env_file_encoding='utf-8',
    )


class AuthSettings(BaseSettings):
    """Настройки авторизации."""

    secret_key: str = secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 60
    algorithm: str = 'HS256'

    model_config = SettingsConfigDict(
        env_prefix='AUTH_',
        env_file='.env',
        env_file_encoding='utf-8',
    )


class Settings(BaseSettings):
    """Корневой класс настроек."""

    database: DatabaseSettings = DatabaseSettings()
    auth: AuthSettings = AuthSettings()

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )


settings = Settings()

MAX_NAME_LENGTH = 100
MAX_ADDRESS_LENGTH = 250
MAX_DESCRIPTION_LENGTH = 500
MAX_USERNAME_LENGTH = 50
MAX_STRING_LENGTH = 255
MAX_PHONE_LENGTH = 32
MAX_PASSWORD_LENGTH = 100
MIN_PASSWORD_LENGTH = 8
MIN_TG_LENGTH = 5
MIN_USERNAME_LENGTH = 6
MAX_TG_LENGTH = 64

BYTES_IN_MB = 1024**2
VALUE_MEMORIE_FILE_MB = 5
COUNT_FILES, MAX_BYTES = 10, BYTES_IN_MB * VALUE_MEMORIE_FILE_MB
