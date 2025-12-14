from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.logging import log_action
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole
from src.users.schemas import UserCreate, UserRead, UserUpdate
from src.users.services import user_crud
from src.users.validators import (check_admin_permission, check_password,
                                  check_user_contacts, check_user_duplicate)

router = APIRouter()


@router.post(
    '/',
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary='Регистрация нового пользователя',
)
@log_action('Регистрация нового пользователя.')
async def register_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles(
            [UserRole.MANAGER, UserRole.ADMIN],
            allow_guest=True,
        ),
    ),
) -> User:
    """Регистрация нового пользователя.

    **Доступ:**
    - неавторизированный пользователь
    - менеджер
    - администратор
    """
    await check_user_duplicate(user_create, session)
    return await user_crud.create(user_create, session)


@router.get(
    '/me',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Получение данных о текущем пользователе',
)
@log_action('Получение данных о текущем пользователе.')
async def get_me(
    current_user: User = Depends(require_roles()),
) -> User:
    """Получение данных о текущем пользователе.

    **Доступ:**
    - авторизированный пользователь
    """
    return current_user


@router.patch(
    '/me',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Обновление данных текущего пользователя',
)
@log_action('Обновление данных текущего пользователя.')
async def update_me(
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_roles()),
) -> User:
    """Обновление данных текущего пользователя.

    Изменение роли и активности доступно только администратору.

    **Доступ:**
    - авторизированный пользователь
    """
    await check_user_duplicate(user_update, session, current_user)
    check_user_contacts(user_update, current_user)
    check_password(user_update, current_user)
    check_admin_permission(user_update, current_user)
    return await user_crud.update(current_user, user_update, session)


@router.get(
    '/',
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary='Получение данных о всех пользователях',
)
@log_action('Получение данных о всех пользователях.')
async def get_all_users(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> list[User]:
    """Получение данных о всех пользователях.

    **Доступ:**
    - менеджер
    - администратор
    """
    return await user_crud.get_multi(session)


@router.get(
    '/{user_id}',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Получение данных пользователя по id',
)
@log_action('Получение данных пользователя по id.')
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> User:
    """Получение данных пользователя по id.

    **Доступ:**
    - менеджер
    - администратор
    """
    user = await user_crud.get(user_id, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Данные не найдены',
        )
    return user


@router.patch(
    '/{user_id}',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Обновление данных пользователя по id',
)
@log_action('Обновление данных пользователя по id.')
async def update_user_by_id(
    user_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> User:
    """Обновление данных пользователя по id.

    Изменение роли и активности доступно только администратору.

    **Доступ:**
    - менеджер
    - администратор
    """
    user = await user_crud.get(user_id, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Данные не найдены',
        )
    await check_user_duplicate(user_update, session, user)
    check_user_contacts(user_update, user)
    check_password(user_update, user)
    check_admin_permission(user_update, current_user)
    return await user_crud.update(user, user_update, session)
