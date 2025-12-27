from pathlib import Path
import secrets

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


MAX_NAME_LENGTH: int = 100
MAX_ADDRESS_LENGTH: int = 250
MAX_DESCRIPTION_LENGTH: int = 500
MAX_USERNAME_LENGTH: int = 50
MAX_STRING_LENGTH: int = 255
MAX_PHONE_LENGTH: int = 32
MAX_PASSWORD_LENGTH: int = 100
MIN_PASSWORD_LENGTH: int = 8
MIN_USERNAME_LENGTH: int = 6
MIN_DESCRIPTION_LENGTH: int = 1
MIN_TG_LENGTH: int = 5
MAX_TG_LENGTH: int = 64
UUID_LENGTH: int = 36
DISH_MIN_PRICE: int = 0
DISH_MAX_PRICE: int = 10000

# Файлы и медиа
BYTES_IN_MB: int = 1024**2
MAX_FILE_SIZE_MB: int = 5
MAX_FILE_SIZE: int = MAX_FILE_SIZE_MB * BYTES_IN_MB
ALLOWED_IMAGE_MIME_TYPES: set[str] = {'image/jpeg', 'image/png'}
VALUE_MEMORIE_FILE_MB: int = 5
COUNT_FILES: int = 10
MAX_BYTES: int = BYTES_IN_MB * VALUE_MEMORIE_FILE_MB

# Пути
BASE_DIR: Path = Path(__file__).resolve().parent.parent
MEDIA_DIR: Path = BASE_DIR / 'media' / 'images'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


class DatabaseSettings(BaseSettings):
    """Настройки базы данных."""

    URL: str = Field(
        default='postgresql+asyncpg://postgres:postgres@localhost:5432/postgres',  # noqa: E501
    )
    POOL_TIMEOUT: PositiveInt = Field(default=30)
    POOL_RECYCLE: PositiveInt = Field(default=1800)
    POOL_SIZE: PositiveInt = Field(default=20)
    MAX_OVERFLOW: PositiveInt = Field(default=30)
    POOL_PING: bool = Field(default=True)
    ECHO_SQL: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix='DATABASE_',
        env_file='.env',
        env_file_encoding='utf-8',
    )


class RedisSettings(BaseSettings):
    """Настройки Redis."""

    URL: str = Field(default='redis://localhost:6379/0')
    PASSWORD: str = Field(default='password')
    SOCKET_CONNECTION_TIMEOUT: PositiveInt = Field(default=5)
    SOCKET_TIMEOUT: PositiveInt = Field(default=5)
    RETRY_ON_TIMEOUT: bool = Field(default=True)
    MAX_CONNECTIONS: PositiveInt = Field(default=10)

    model_config = SettingsConfigDict(
        env_prefix='REDIS_',
        env_file='.env',
        env_file_encoding='utf-8',
    )


class AuthSettings(BaseSettings):
    """Настройки авторизации."""

    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: PositiveInt = 6000
    ALGORITHM: str = 'HS256'

    model_config = SettingsConfigDict(
        env_prefix='AUTH_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
    )


class Settings(BaseSettings):
    """Корневой класс настроек."""

    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
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

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * BYTES_IN_MB
ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png'}
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / 'media' / 'images'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
