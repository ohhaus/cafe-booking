from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


MAX_NAME_LENGTH = 100
MAX_ADDRESS_LENGTH = 250
MAX_PHONE_LENGTH = 32
MAX_DESCRIPTION_LENGTH = 500


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


class Settings(BaseSettings):
    """Корневой класс настроек."""

    database: DatabaseSettings = DatabaseSettings()

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )


settings = Settings()
