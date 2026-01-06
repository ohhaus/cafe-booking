from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import EmailStr, Field, PositiveInt
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
DISH_MIN_PRICE: Decimal = Decimal('0')
DISH_MAX_PRICE: Decimal = Decimal('10000.00')

# Файлы и медиа
BYTES_IN_MB: int = 1024**2
MAX_FILE_SIZE_MB: int = 5
MAX_FILE_SIZE: int = MAX_FILE_SIZE_MB * BYTES_IN_MB
ALLOWED_IMAGE_MIME_TYPES: set[str] = {'image/jpeg', 'image/png'}
VALUE_MEMORIE_FILE_MB: int = 5
COUNT_FILES: int = 10
MAX_BYTES: int = BYTES_IN_MB * VALUE_MEMORIE_FILE_MB

# Пути
BASE_DIR: Path = Path('/app')
MEDIA_DIR: Path = BASE_DIR / 'media' / 'images'


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
        extra='ignore',
    )


class RedisSettings(BaseSettings):
    """Настройки Redis."""

    URL: str = Field(default='redis://redis:6379/0')
    PASSWORD: str = Field(default='password')
    SOCKET_CONNECTION_TIMEOUT: PositiveInt = Field(default=5)
    SOCKET_TIMEOUT: PositiveInt = Field(default=5)
    RETRY_ON_TIMEOUT: bool = Field(default=True)
    MAX_CONNECTIONS: PositiveInt = Field(default=10)

    model_config = SettingsConfigDict(
        env_prefix='REDIS_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


class CacheSettings(BaseSettings):
    """Настройка кэширования."""

    TTL_CAFES_LIST: PositiveInt = Field(default=600)  # 10 минут
    TTL_CAFE_BY_ID: PositiveInt = Field(default=1800)  # 30 минут
    TTL_CAFE_ACTIVE: PositiveInt = Field(default=300)  # 5 минут
    TTL_DISHES_LIST: PositiveInt = Field(default=900)  # 15 минут
    TTL_DISH_BY_ID: PositiveInt = Field(default=1800)  # 30 минут
    TTL_ACTIONS_LIST: PositiveInt = Field(default=300)  # 5 минут
    TTL_ACTION_BY_ID: PositiveInt = Field(default=900)  # 15 минут
    TTL_CAFE_TABLES: PositiveInt = Field(default=120)  # 2 минуты
    TTL_CAFE_TABLE: PositiveInt = Field(default=300)  # 5 минут
    TTL_CAFE_TABLE_ACTIVE: PositiveInt = Field(default=300)  # 5 минут
    TTL_CAFE_SLOTS: PositiveInt = Field(default=120)  # 2 минуты
    TTL_CAFE_SLOT: PositiveInt = Field(default=300)  # 5 минуты
    TTL_CAFE_SLOT_ACTIVE: PositiveInt = Field(default=300)  # 5 минут
    TTL_MEDIA: PositiveInt = Field(default=3600)  # 60 минут
    TTL_MANAGER_CUD_CAFE: PositiveInt = Field(default=120)  # 2 минуты
    TTL_CAFE_META: PositiveInt = Field(default=120)  # 2 минуты

    model_config = SettingsConfigDict(
        env_prefix='CACHE_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


class AuthSettings(BaseSettings):
    """Настройки авторизации."""

    SECRET_KEY: str = Field(default='super-secret-key')
    ACCESS_TOKEN_EXPIRE_MINUTES: PositiveInt = 6000
    ALGORITHM: str = 'HS256'

    model_config = SettingsConfigDict(
        env_prefix='AUTH_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
    )


class CelerySettings(BaseSettings):
    """Настройка Celery."""

    # Номер Redis DB для брокера (очереди задач). 0 = первая база Redis
    BROKER_DB: int = Field(default=1)
    # Номер Redis DB для result-backend (хранение результатов). Отдельная база,
    # чтобы не мешать очереди
    RESULT_DB: int = Field(default=2)
    # Таймзона Celery/Beat: влияет на расписания crontab и время
    # выполнения периодических задач
    TIMEZONE: str = Field(default='Europe/Moscow')
    # Включить использование UTC внутри Celery (обычно True).
    # Celery хранит времена в UTC, а отображает в timezone
    ENABLE_UTC: bool = Field(default=True)
    # Формат сериализации тела задачи (аргументы/kwargs) при отправке в брокер.
    # JSON = безопасно и стандартно
    TASK_SERIALIZER: str = Field(default='json')
    # Формат сериализации результата выполнения задачи в backend.
    # JSON = проще для анализа/дебага
    RESULT_SERIALIZER: str = Field(default='json')
    # Какие форматы вообще принимать.
    # Ограничение до json защищает от pickle-инъекций
    ACCEPT_CONTENT: list[str] = Field(default_factory=lambda: ['json'])
    # Игнорировать результаты задач
    # (True экономит место в backend, если return не нужен)
    TASK_IGNORE_RESULT: bool = Field(default=False)
    # Отмечать статус STARTED
    # (помогает мониторингу понять, что задача реально началась)
    TASK_TRACK_STARTED: bool = Field(default=True)
    # Повторять подключение к брокеру при старте
    # (важно в Docker, когда Redis поднимается позже)
    BROKER_CONNECTION_RETRY_ON_STARTUP: bool = Field(default=True)
    # Жёсткий лимит времени выполнения задачи (сек).
    # По истечении Celery принудительно убьёт задачу
    TASK_TIME_LIMIT: PositiveInt = Field(default=300)
    # Мягкий лимит (сек): сначала кидает SoftTimeLimitExceeded,
    # чтобы ты мог корректно завершиться
    TASK_SOFT_TIME_LIMIT: PositiveInt = Field(default=240)
    # Доп. опции транспорта брокера (для Redis — настройки поведения очереди)
    BROKER_TRANSPORT_OPTIONS: dict[str, Any] = Field(
        default_factory=lambda: {
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True,
        },
    )

    model_config = SettingsConfigDict(
        env_prefix='CELERY_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


class MailSettings(BaseSettings):
    """Настройки отправки почты (SMTP)."""

    USERNAME: str = Field(default='noreply@example.com')
    PASSWORD: str = Field(default='change-me')
    FROM: EmailStr = Field(default='noreply@example.com')
    PORT: int = Field(default=465)
    SERVER: str = Field(default='smtp.server.com')
    TLS: bool = Field(default=False)
    SSL: bool = Field(default=True)
    FROM_NAME: str = Field(default='Cafe Booking System')
    USE_CREDENTIALS: bool = Field(default=True)
    VALIDATE_CREDS: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_prefix='MAIL_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


class SuperUserSettings(BaseSettings):
    """Настройки для создания супепользователя."""

    USERNAME: str = Field(default='ohhaus')
    EMAIL: str = Field(default='admin@example.com')
    PHONE: str = Field(default='+79776667766')
    PASSWORD: str = Field(default='AdminSecure123!')
    TG_ID: str = Field(default='123456789')

    model_config = SettingsConfigDict(
        env_prefix='SUPERUSER_',
        env_file='.env',
        env_file_encoding='utf-8',
    )


class Settings(BaseSettings):
    """Корневой класс настроек."""

    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    cache: CacheSettings = CacheSettings()
    auth: AuthSettings = AuthSettings()
    celery: CelerySettings = CelerySettings()
    mail: MailSettings = MailSettings()
    superuser: SuperUserSettings = SuperUserSettings()

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )


settings = Settings()
