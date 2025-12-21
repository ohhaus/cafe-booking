from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import DatabaseService
from src.users.models import User, UserRole
from src.users.schemas import UserCreate, UserUpdate
from src.users.security import get_password_hash


class UserService(DatabaseService[User, UserCreate, UserUpdate]):
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
    ) -> User | None:
        """Получает пользователя по email или телефону."""
        login_value = login_data.login

        # Поиск пользователя по email или телефону
        query = select(self.model).where(
            (
                self.model.email == login_value
                ) | (self.model.phone == login_value),
        )
        result = await session.execute(query)
        return result.scalars().first()

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
