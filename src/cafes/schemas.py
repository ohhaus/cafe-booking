from typing import Optional
import uuid

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)
from pydantic_extra_types.phone_numbers import PhoneNumber

from src.config import (
    MAX_ADDRESS_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
)


#  Валидацию входящих объектов нужно вынести в отдельный модуль.
class PhoneE164(PhoneNumber):
    """Формат телефонного номера."""

    phone_format = 'E164'


class CafeBase(BaseModel):
    """Базовая схема кафе."""

    name: str = Field(
        ...,
        max_length=MAX_NAME_LENGTH,
        title='Название кафе',
    )
    address: str = Field(
        ...,
        max_length=MAX_ADDRESS_LENGTH,
        title='Адрес кафе',
    )
    phone: PhoneE164 = Field(
        ...,
        max_length=MAX_PHONE_LENGTH,
        title='Телефон кафе',
    )
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        title='Описание кафе',
    )


class CafeCreate(CafeBase):
    """Схема создания кафе."""

    manager_ids: list[uuid.UUID] = Field(
        default_factory=list,
        title='ID менеджеров кафе',
    )
    photo_id: Optional[uuid.UUID] = Field(
        None,
        title='ID фотографии кафе',
    )

    @field_validator('manager_ids')
    def check_manager_ids_not_empty(
        self,
        values: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        """Проверка, что список менеджеров не пустой."""
        if not values:
            raise ValueError(
                'Необходимо указать хотя бы одного менеджера кафе.',
            )
        return values


class CafeUpdate(BaseModel):
    """Схема обновления кафе.

    Для поля manager_ids:
        None -> не изменяет список менеджеров;
        []   -> очищает список менеджеров;
        [..] -> перезаписывает список.
    """

    name: Optional[str] = Field(
        None,
        max_length=MAX_NAME_LENGTH,
        title='Название кафе',
    )
    address: Optional[str] = Field(
        None,
        max_length=MAX_ADDRESS_LENGTH,
        title='Адрес кафе',
    )
    phone: Optional[PhoneE164] = Field(
        None,
        max_length=MAX_PHONE_LENGTH,
        title='Телефон кафе',
    )
    description: Optional[str] = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        title='Описание кафе',
    )
    manager_ids: Optional[list[uuid.UUID]] = Field(
        default=None,
        title='Новый список id менеджеров кафе',
    )
    photo_id: Optional[uuid.UUID] = Field(
        default=None,
        title='ID фотографии кафе',
    )


class CafeInDBBase(CafeBase):
    """Базовая схема кафе в БД."""

    id: uuid.UUID = Field(title='ID кафе')
    photo_id: Optional[uuid.UUID] = Field(
        None,
        title='ID фотографии кафе',
    )

    class Config:
        from_attributes = True


class CafeOut(CafeInDBBase):
    """Схема кафе для ответа API."""

    manager_ids: list[uuid.UUID] = Field(
        default_factory=list,
        title='ID менеджеров кафе',
    )
