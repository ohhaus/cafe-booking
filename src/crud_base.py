from typing import Any, Generic, Type, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, User

ModelType = TypeVar('ModelType', bound=Base)


class CRUDBase(Generic[ModelType]):
    """Базовый класс для CRUD-операций."""

    def __init__(self, model: Type[ModelType]) -> None:
        """Инициализирует класс."""
        self.model = model

    async def get(
        self,
        obj_id: int,
        session: AsyncSession,
    ) -> ModelType | None:
        """Получает объект по его ID."""
        db_obj = await session.execute(
            select(self.model).where(
                self.model.id == obj_id,
            ),
        )
        return db_obj.scalars().first()

    async def get_multi(
        self,
        session: AsyncSession,
    ) -> list[ModelType]:
        """Получает все объекты модели."""
        db_objs = await session.execute(select(self.model))
        return db_objs.scalars().all()

    async def create(
        self,
        obj_in: BaseModel,
        session: AsyncSession,
        user: User | None = None,
    ) -> ModelType:
        """Создает новый объект на основе входных данных."""
        obj_in_data = obj_in.dict()
        if user is not None:
            obj_in_data['user_id'] = user.id
        db_obj = self.model(**obj_in_data)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db_obj: ModelType,
        obj_in: BaseModel,
        session: AsyncSession,
    ) -> ModelType:
        """Обновляет существующий объект новыми данными."""
        obj_data = jsonable_encoder(db_obj)
        update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def exists(
        self,
        session: AsyncSession,
        **kwargs: Any,
    ) -> bool:
        """Проверяет существование записи по переданным значениям."""
        filters = []
        for key, value in kwargs.items():
            field = getattr(self.model, key)
            if isinstance(value, list):
                filters.append(field.in_(value))
            elif isinstance(value, bool):
                filters.append(field.is_(value))
            else:
                filters.append(field == value)
        stmt = select(exists().where(and_(*filters)))
        return bool(await session.scalar(stmt))

    async def count(
        self,
        session: AsyncSession,
        **filters: Any,
    ) -> int:
        """Подсчитывает количество записей по переданным фильтрам."""
        filter_conditions = []
        for key, value in filters.items():
            field = getattr(self.model, key)
            if isinstance(value, list):
                filter_conditions.append(field.in_(value))
            elif isinstance(value, bool):
                filter_conditions.append(field.is_(value))
            else:
                filter_conditions.append(field == value)
        query = (
            select(
                func.count(),
            )
            .select_from(self.model)
            .where(and_(*filter_conditions))
        )
        return int(await session.execute(query).scalar() or 0)
