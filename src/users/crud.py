from typing import Any

from fastapi.encoders import jsonable_encoder
from models import User, UserRole
from schemas import UserCreate, UserUpdate
from security import get_password_hash
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_base import CRUDBase


class UserService(CRUDBase):
    """CRUD для модели User."""

    async def create(
        self,
        obj_in: UserCreate,
        session: AsyncSession,
    ) -> User:
        """Создает новый объект на основе входных данных."""
        obj_in_data = obj_in.model_dump()
        obj_in_data['hashed_password'] = get_password_hash(
            obj_in_data.pop('password'),
        )
        db_obj = self.model(**obj_in_data)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db_obj: User,
        obj_in: UserUpdate,
        session: AsyncSession,
    ) -> User:
        """Обновляет существующий объект новыми данными."""
        obj_data = jsonable_encoder(db_obj)
        update_data = obj_in.model_dump(exclude_unset=True)
        if update_data.get('password'):
            update_data['hashed_password'] = get_password_hash(
                update_data.pop('password'),
            )
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def get_by_login_data(
        self,
        login_data: dict[str, Any],
        session: AsyncSession,
    ) -> list[User]:
        """Получает объекты модели, если совпадает хотя бы одно поле."""
        if not login_data:
            return []
        conditions = []
        for field_name, value in login_data.items():
            field = getattr(self.model, field_name, None)
            if field is None:
                raise ValueError(
                    f'Поле "{field_name}" не найдено '
                    f'в модели {self.model.__name__}',
                )
            conditions.append(field == value)

        stmt = select(self.model).where(or_(*conditions))
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_active_role_by_ids(
        self,
        ids: list,
        role: UserRole,
        session: AsyncSession,
    ) -> list[User]:
        """Получает активные объекты модели, исходя из списка id и роли."""
        if not ids:
            return []
        stmt = select(self.model).where(
            and_(
                self.model.role == role,
                self.model.is_active,
                self.model.id.in_(ids),
            ),
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_active_by_role(
        self,
        role: UserRole,
        session: AsyncSession,
    ) -> list[User]:
        """Получает активные объекты модели, исходя из роли."""
        stmt = select(self.model).where(
            and_(
                self.model.role == role,
                self.model.is_active,
            ),
        )
        result = await session.execute(stmt)
        return result.scalars().all()


user_crud = UserService(User)
