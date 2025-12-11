import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Настройки базы данных."""

    URL: str = Field(default='postgresql+asyncpg://postgres:postgres@localhost:5432/postgres')
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


BASE_CONFIG = DatabaseSettings.model_config


class AuthSettings(BaseSettings):
    """Настройки авторизации."""

    secret_key: str = secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 60
    algorithm: str = 'HS256'

    model_config = BASE_CONFIG | {'env_prefix': 'AUTH_'}


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
