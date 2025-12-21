from __future__ import annotations

from typing import Any, MutableMapping, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.cafes.models import Cafe
from src.users.models import User


ModelT = TypeVar('ModelT')


async def get_cafe_or_none(
    db: AsyncSession,
    cafe_id: UUID,
) -> Optional[Cafe]:
    """Запрос к БД на получение кафе по UUID."""
    result = await db.execute(select(Cafe).where(Cafe.id == cafe_id))
    return result.scalars().first()


def require_staff(
    user: User,
    message: str,
) -> None:
    """Проверяет, что запрос выполняет staff-пользователь (admin/manager).

    Используется в сервисах, где операция запрещена обычным пользователям.
    Если пользователь не staff — выбрасывает PermissionError
    с заданным сообщением.
    """
    if not user.is_staff():
        raise PermissionError(message)


def cafe_scoped_stmt(
    model: Type[ModelT],
    cafe_id: UUID,
    *,
    cafe_fk_field: str = 'cafe_id',
) -> Select:
    """Базовый SELECT для моделей, привязанных к кафе через FK.

    Формирует выражение вида:
        SELECT model WHERE model.<cafe_fk_field> = cafe_id.
    """
    return select(model).where(
        getattr(model, cafe_fk_field) == cafe_id,
    )


def with_id(
    stmt: Select,
    model: Type[ModelT],
    obj_id: UUID,
    *,
    id_field: str = 'id',
) -> Select:
    """Добавляет фильтр по первичному ключу к существующему SELECT.

    Формирует дополнение вида:
        ... WHERE model.<id_field> = obj_id.
    """
    return stmt.where(getattr(model, id_field) == obj_id)


def apply_visibility_filters(
    stmt: Select,
    model: Type[ModelT],
    current_user: User,
    *,
    show_all: Optional[bool] = None,
    active_field: str = 'active',
    cafe_fk_field: str = 'cafe_id',
) -> Select:
    """Применяет общие правила видимости для сущностей, привязанных к кафе.

    Правила:
      - Staff-пользователь:
          * show_all=False -> только активные сущности
          (model.<active_field> = True)
          * show_all=True/None -> все сущности
      - Обычный пользователь:
          * только активные сущности
          * и только если Cafe.active=True (через JOIN по cafe_id).
    """
    active_col = getattr(model, active_field)

    if current_user.is_staff():
        if show_all is False:
            return stmt.where(active_col.is_(True))
        return stmt

    cafe_fk_col = getattr(model, cafe_fk_field)
    return (
        stmt.where(active_col.is_(True))
        .join(Cafe, Cafe.id == cafe_fk_col)
        .where(Cafe.active.is_(True))
    )


def rename_payload_key(
    payload: MutableMapping[str, Any],
    *,
    api_field: str,
    model_field: str,
) -> MutableMapping[str, Any]:
    """Переименовывает ключ в payload из api_field в model_field.

    Полезно для маппинга полей между API-схемами и ORM-моделями.
    Например: is_active -> active.
    """
    if api_field in payload:
        payload[model_field] = payload.pop(api_field)
    return payload
