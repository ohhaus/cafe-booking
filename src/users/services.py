from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import DatabaseService
from src.users.models import User, UserRole
from src.users.schemas import AuthData, UserCreate, UserUpdate
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
        update_data = obj_in.model_dump(exclude_unset=True, exclude_none=True)

        if 'is_active' in update_data:
            update_data['active'] = update_data.pop('is_active')

        if update_data.get('password'):
            update_data['hashed_password'] = get_password_hash(
                update_data.pop('password'),
            )
        for field, value in update_data.items():
            setattr(db_obj, field, update_data[field])

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def get_by_login_data(
        self,
        login_data: dict[str, Any] | AuthData,
        session: AsyncSession,
    ) -> User | None:
        """Получает пользователя по логину (email или phone)."""
        if isinstance(login_data, AuthData):
            stmt = select(self.model).where(
                or_(
                    self.model.email == login_data.login,
                    self.model.phone == login_data.login,
                ),
            )
        else:
            if not login_data:
                return None
            conditions = []
            for field_name, value in login_data.items():
                field = getattr(self.model, field_name, None)
                if field is None:
                    raise ValueError(
                        f'Поле "{field_name}" не найдено в модели '
                        f'{self.model.__name__}',
                    )
                conditions.append(field == value)
            stmt = select(self.model).where(or_(*conditions))

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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
                self.model.active,
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
                self.model.active,
            ),
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_by_username(
        self,
        username: str,
        session: AsyncSession,
    ) -> User | None:
        """Получает пользователя по имени пользователя."""
        stmt = select(self.model).where(self.model.username == username)
        result = await session.execute(stmt)
        return result.scalars().first()


user_crud = UserService(User)
