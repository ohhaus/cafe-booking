from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User, UserRole
from src.users.schemas import UserCreate, UserUpdate
from src.users.security import verify_password
from src.users.services import user_crud


async def check_user_duplicate(
    user_data: UserCreate | UserUpdate,
    session: AsyncSession,
    updated_user: User | None = None,
) -> None:
    """Проверяет пользователя на уникальность при создании и при обновлении."""
    unique_fields = ('username', 'email', 'phone', 'tg_id')
    login_data = user_data.model_dump(exclude_unset=True)
    login_data = {
        k: v
        for k, v in login_data.items()
        if k in unique_fields and v is not None
    }

    if not login_data:
        return

    for field, value in login_data.items():
        if field == 'username':
            user = await user_crud.get_by_username(value, session)
        else:
            from sqlalchemy import select

            from src.users.models import User

            stmt = select(User).where(getattr(User, field) == value)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

        if user:
            if updated_user and updated_user.id == user.id:
                continue
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Пользователь с такими данными уже существует!',
            )


def check_user_contacts(user_update: UserUpdate, user: User) -> None:
    """Проверяет наличие контактных данных при обновлении."""
    data = user_update.model_dump(exclude_unset=True, exclude_none=True)
    phone = data.get('phone', user.phone)
    email = data.get('email', user.email)

    if not phone and not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Нельзя удалить свой единственный контакт!',
        )


def check_admin_permission(
    user_update: UserUpdate,
    current_user: User,
    target_user: User | None = None,
) -> None:
    """Проверяет возможность персонала менять роль пользователя."""
    data = user_update.model_dump(exclude_unset=True, exclude_none=True)

    if 'role' in data and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='У вас нет прав на изменение роли пользователя!',
        )

    if 'is_active' in data and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='У вас нет прав на изменение активности пользователя!',
        )

    if target_user and target_user.id == current_user.id:
        if 'role' in data or 'is_active' in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=('Вы не можете изменить свою собственную роль!'),
            )


def check_password(user_update: UserUpdate, user: User) -> None:
    """Проверяет, чтоб пароль не повторялся."""
    if user_update.password:
        if verify_password(user_update.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Вы уже используйте этот пароль!',
            )
