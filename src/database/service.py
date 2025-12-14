"""Базовый сервисный слой для работы с БД."""

from typing import Any, Generic, Sequence, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import Base

ModelType = TypeVar('ModelType', bound=Base)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)


class DatabaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Базовый сервис для операций с БД.

    Предоставляет стандартные CRUD операции для всех моделей.

    Args:
        model: SQLAlchemy модель для выполнения операций

    Example:
        class UserService(DatabaseService[User, UserCreate, UserUpdate]):
            pass

        user_service = UserService(User)

    """

    def __init__(self, model: Type[ModelType]) -> None:
        """Инициализирует сервис с указанной моделью."""
        self.model = model

    async def get(
        self,
        session: AsyncSession,
        *,
        id: int,
    ) -> ModelType | None:
        """Получает объект по ID.

        Args:
            session: Асинхронная сессия БД
            id: Идентификатор объекта

        Returns:
            Объект модели или None если не найден

        """
        result = await session.execute(
            select(self.model).where(self.model.id == id),
        )
        return result.scalars().first()

    async def get_multi(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelType]:
        """Получает список объектов с пагинацией.

        Args:
            session: Асинхронная сессия БД
            skip: Количество пропускаемых записей
            limit: Максимальное количество возвращаемых записей

        Returns:
            Последовательность объектов модели

        """
        result = await session.execute(
            select(self.model).offset(skip).limit(limit),
        )
        return result.scalars().all()

    async def create(
        self,
        session: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        commit: bool = True,
    ) -> ModelType:
        """Создает новый объект.

        Args:
            session: Асинхронная сессия БД
            obj_in: Схема с данными для создания
            commit: Выполнять ли commit сразу

        Returns:
            Созданный объект модели

        """
        # Pydantic v2 compatibility
        obj_in_data = (
            obj_in.model_dump()
            if hasattr(obj_in, 'model_dump')
            else obj_in.dict()
        )

        db_obj = self.model(**obj_in_data)
        session.add(db_obj)

        if commit:
            await session.commit()
            await session.refresh(db_obj)

        return db_obj

    async def update(
        self,
        session: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
        commit: bool = True,
    ) -> ModelType:
        """Обновляет существующий объект.

        Args:
            session: Асинхронная сессия БД
            db_obj: Объект для обновления
            obj_in: Схема или словарь с данными для обновления
            commit: Выполнять ли commit сразу

        Returns:
            Обновленный объект модели

        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Pydantic v2 compatibility
            update_data = (
                obj_in.model_dump(exclude_unset=True)
                if hasattr(obj_in, 'model_dump')
                else obj_in.dict(exclude_unset=True)
            )

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        session.add(db_obj)

        if commit:
            await session.commit()
            await session.refresh(db_obj)

        return db_obj

    async def delete(
        self,
        session: AsyncSession,
        *,
        id: int,
        commit: bool = True,
    ) -> ModelType | None:
        """Удаляет объект по ID.

        Args:
            session: Асинхронная сессия БД
            id: Идентификатор объекта для удаления
            commit: Выполнять ли commit сразу

        Returns:
            Удаленный объект или None если не найден

        """
        db_obj = await self.get(session=session, id=id)

        if db_obj:
            await session.delete(db_obj)

            if commit:
                await session.commit()

        return db_obj

    async def exists(
        self,
        session: AsyncSession,
        **filters: Any,
    ) -> bool:
        """Проверяет существование записи по фильтрам.

        Args:
            session: Асинхронная сессия БД
            **filters: Фильтры для поиска (поле=значение)

        Returns:
            True если запись существует, иначе False

        Example:
            exists = await service.exists(
                session=session,
                email="user@example.com",
                is_active=True,
            )

        """
        conditions = self._build_filter_conditions(**filters)
        stmt = select(exists().where(and_(*conditions)))
        result = await session.execute(stmt)
        return bool(result.scalar())

    async def count(
        self,
        session: AsyncSession,
        **filters: Any,
    ) -> int:
        """Подсчитывает количество записей по фильтрам.

        Args:
            session: Асинхронная сессия БД
            **filters: Фильтры для поиска (поле=значение)

        Returns:
            Количество найденных записей

        Example:
            count = await service.count(
                session=session,
                is_active=True,
                role=["admin", "manager"],
            )

        """
        conditions = self._build_filter_conditions(**filters)
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(and_(*conditions))
        )
        result = await session.execute(stmt)
        return int(result.scalar() or 0)

    def _build_filter_conditions(self, **filters: Any) -> list:
        """Строит список условий для фильтрации.

        Вспомогательный метод для построения SQLAlchemy условий.

        Args:
            **filters: Фильтры (поле=значение)

        Returns:
            Список SQLAlchemy условий

        """
        conditions = []

        for key, value in filters.items():
            if not hasattr(self.model, key):
                continue

            field = getattr(self.model, key)

            if isinstance(value, list):
                conditions.append(field.in_(value))
            elif isinstance(value, bool):
                conditions.append(field.is_(value))
            elif value is None:
                conditions.append(field.is_(None))
            else:
                conditions.append(field == value)

        return conditions
