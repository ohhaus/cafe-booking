from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from security import verify_password
from crud import user_crud
from models import User, UserRole
from schemas import UserCreate, UserUpdate


async def check_user_duplicate(
    user_data: UserCreate | UserUpdate,
    session: AsyncSession,
    updated_user: User | None = None,
) -> None:
    """Проверяет пользователя на уникальность при создании и при обновлении."""
    unique_fields = ('username', 'email', 'phone', 'tg_id')
    login_data = user_data.model_dump(exclude_unset=True)
    login_data = {k: v for k, v in login_data.items() if k in unique_fields}
    users = await user_crud.get_by_login_data(login_data, session)
    for user in users:
        if updated_user and updated_user.id == user.id:
            continue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Пользователь с такими данными уже существует!',
        )


def check_user_contacts(user_update: UserUpdate, user: User) -> None:
    """Проверяет наличие контактных данных при обновлении."""
    data = user_update.model_dump(exclude_unset=True)
    phone = data.get('phone', user.phone)
    email = data.get('email', user.email)

    if not phone and not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Нельзя удалить свой единственный контакт!',
        )


def check_admin_permission(user_update: UserUpdate, user: User) -> None:
    """Проверяет наличие возможность персонала менять роль пользователя."""
    if isinstance(user_update.role, UserRole) and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='У вас нет прав на изменение роли пользователя!',
        )
    if isinstance(user_update.is_active, bool) and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='У вас нет прав на изменение активности пользователя!',
        )


def check_password(user_update: UserUpdate, user: User) -> None:
    """Проверяет, чтоб пароль не повторялся."""
    if user_update.password:
        if verify_password(user_update.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Вы уже используйте этот пароль!',
            )
