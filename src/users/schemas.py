import re
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    PlainValidator,
    field_validator,
    model_validator,
)
from pydantic_extra_types.phone_numbers import PhoneNumber
from python_usernames import is_safe_username

from src.common import BaseRead
from src.config import (
    MAX_PASSWORD_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    MIN_TG_LENGTH,
    MIN_USERNAME_LENGTH,
)
from src.users.models import UserRole


class PhoneE164(PhoneNumber):
    """Валидация номеров."""

    phone_format = 'E164'


def validate_password(value: str | None) -> str | None:
    """Проверка пароля."""
    if value is None:
        return None
    if not re.search(r'[A-Z]', value):
        raise ValueError(
            'Пароль должен содержать хотя бы одну заглавную букву',
        )
    if not re.search(r'[a-z]', value):
        raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
    if not re.search(r'\d', value):
        raise ValueError('Пароль должен содержать хотя бы одну цифру')
    if not re.search(r'[!@#$%^&*(),.?{}|<>_]', value):
        raise ValueError('Пароль должен содержать хотя бы один спецсимвол')
    return value


def validate_username(value: str | None) -> str | None:
    """Проверка имени пользователя."""
    if value is None:
        return None
    if not is_safe_username(value):
        raise ValueError('Недопустимое имя пользователя')
    return value


PasswordStr = Annotated[
    str,
    Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description=(
            f'Пароль: минимум {MIN_PASSWORD_LENGTH} символов, включая цифру, '
            'заглавную букву и спецсимвол'
        ),
        examples=['pasS_123'],
    ),
    PlainValidator(validate_password),
]

UsernameStr = Annotated[
    str,
    Field(
        min_length=MIN_USERNAME_LENGTH,
        max_length=MAX_USERNAME_LENGTH,
        pattern=r'^[a-zA-Z0-9_.-]+$',
        description=(
            f'Имя пользователя: {MIN_USERNAME_LENGTH}–{MAX_USERNAME_LENGTH} '
            'символов, буквы/цифры/_.-'
        ),
        examples=['example_user1'],
    ),
    PlainValidator(validate_username),
]

TagIdStr = Annotated[
    str,
    Field(
        min_length=MIN_TG_LENGTH,
        pattern=r'^\d+$',
        description=f'Telegram ID: минимум {MIN_TG_LENGTH} символов',
        examples=['12345'],
    ),
]

PhoneStr = Annotated[
    PhoneE164,
    Field(
        description='Номер телефона',
        examples=['+375291111111'],
    ),
]


class Token(BaseModel):
    """Схема для токена."""

    access_token: str
    token_type: str = 'bearer'


class AuthData(BaseModel):
    """Схема для авторизации."""

    login: str = Field(
        ...,
        description='Логин пользователя (email или телефон)',
    )
    password: str = Field(..., description='Пароль пользователя')

    model_config = ConfigDict(from_attributes=True)


class RoleMixin(BaseModel):
    """Схема для поля роль."""

    role: UserRole | None = None


class BaseUser(BaseModel):
    """Базовая схема для пользователя."""

    email: EmailStr | None = Field(None, validate_default=False)
    phone: PhoneStr | None = Field(None, validate_default=False)
    tg_id: TagIdStr | None = Field(None, validate_default=False)

    model_config = ConfigDict(extra='forbid')


class UserRead(BaseRead, BaseUser, RoleMixin):
    """Схема для чтения данных пользователя."""

    username: UsernameStr
    is_active: bool = Field(alias='active')

    model_config = ConfigDict(from_attributes=True)


class UserReadView(BaseUser):
    """Схема для представления пользователя в выводе кафе и бронирования."""

    id: UUID
    username: UsernameStr


class UserCreate(BaseUser):
    """Схема для создания пользователя."""

    username: UsernameStr
    password: PasswordStr

    @model_validator(mode='after')
    def check_contact(self) -> 'UserCreate':
        """Проверка наличия email или phone."""
        if not self.email and not self.phone:
            raise ValueError('Необходимо указать email или телефон')
        return self


class UserUpdate(BaseUser, RoleMixin):
    """Схема для обновления пользователя."""

    username: UsernameStr | None = None
    password: PasswordStr | None = None
    is_active: bool | None = Field(None, alias='active')

    @field_validator('password', mode='before')
    @classmethod
    def validate_password_none(cls, v: Any) -> Any:
        """Разрешаем None для пароля."""
        return v

    @field_validator('username', mode='before')
    @classmethod
    def validate_username_none(cls, v: Any) -> Any:
        """Разрешаем None для username."""
        return v

    @model_validator(mode='after')
    def forbid_nulls(self) -> Self:
        """Проверка полей на null."""
        for field in ('username', 'password', 'role', 'is_active'):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f'Поле {field} не может быть null')
        return self

    @model_validator(mode='after')
    def check_contact(self) -> Self:
        """Проверка наличия email или phone при обновлении."""
        return self


class AdminUserCreate(UserCreate, RoleMixin):
    """Схема для создания пользователя с ролью."""

    pass


class AuthToken(BaseModel):
    """Схема для ответа с токеном."""

    access_token: str
    token_type: str = 'bearer'

    model_config = ConfigDict(from_attributes=True)
