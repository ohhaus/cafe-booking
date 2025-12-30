from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.logging import log_action
from src.database.sessions import get_async_session
from src.users.dependencies import require_roles
from src.users.models import User, UserRole
from src.users.responses import (
    USER_CREATE_RESPONSES,
    USER_LIST_RESPONSES,
    USER_ME_PATCH_RESPONSES,
    USER_RETRIEVE_RESPONSES,
    USER_UPDATE_RESPONSES,
)
from src.users.schemas import UserCreate, UserRead, UserUpdate
from src.users.services import user_crud
from src.users.validators import (
    check_admin_permission,
    check_password,
    check_user_contacts,
    check_user_duplicate,
)


router = APIRouter()


@router.post(
    '/',
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary='Регистрация нового пользователя',
    description=(
        'Создает нового пользователя с указанными данными. <br><br>'
        '<b>Обязательные поля:</b> <ul><li>username</li><li>password</li>'
        '<li>email или phone</li></ul>'
    ),
    responses=USER_CREATE_RESPONSES,
)
@log_action('Регистрация нового пользователя.')
async def register_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User | None = Depends(
        require_roles(
            [UserRole.MANAGER, UserRole.ADMIN],
            allow_guest=True,
        ),
    ),
) -> User:
    """Регистрация нового пользователя."""
    await check_user_duplicate(user_create, session)
    return await user_crud.create(user_create, session)


@router.get(
    '/me',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Получение информации о текущем пользователе',
    description=(
        'Возвращает информацию о текущем пользователе. Только для '
        'авторизированных пользователей'
    ),
    responses=USER_LIST_RESPONSES,
)
@log_action('Получение данных о текущем пользователе.')
async def get_me(
    current_user: User = Depends(require_roles()),
) -> User:
    """Получение данных о текущем пользователе."""
    return current_user


@router.patch(
    '/me',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Обновление информации о текущем пользователе',
    description=(
        'Возвращает обновленную информацию о пользователе. Только для '
        'авторизированных пользователей'
    ),
    responses=USER_ME_PATCH_RESPONSES,
)
@log_action('Обновление данных текущего пользователя.')
async def update_me(
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_roles()),
) -> User:
    """Обновление данных текущего пользователя."""
    await check_user_duplicate(user_update, session, current_user)
    check_user_contacts(user_update, current_user)
    check_password(user_update, current_user)
    check_admin_permission(user_update, current_user, current_user)
    return await user_crud.update(current_user, user_update, session)


@router.get(
    '/',
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary='Получение списка пользователей',
    description=(
        'Возвращает информацию о всех пользователях. Только для '
        'администраторов или менеджеров'
    ),
    responses=USER_LIST_RESPONSES,
)
@log_action('Получение данных о всех пользователях.')
async def get_all_users(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> list[User]:
    """Получение данных о всех пользователях."""
    return await user_crud.get_multi(session)


@router.get(
    '/{user_id}',
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary='Получение информации о пользователе по его ID',
    description=(
        'Возвращает информацию о пользователе по его ID. Только для '
        'администраторов или менеджеров'
    ),
    responses=USER_RETRIEVE_RESPONSES,
)
@log_action('Получение данных пользователя по id.')
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> User:
    """Получение данных пользователя по id."""
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
    summary='Обновление информации о пользователе по его ID',
    description=(
        'Возвращает обновленную информацию о пользователе по его ID. '
        'Только для администраторов или менеджеров'
    ),
    responses=USER_UPDATE_RESPONSES,
)
@log_action('Обновление данных пользователя по id.')
async def update_user_by_id(
    user_id: UUID,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN]),
    ),
) -> User:
    """Обновление данных пользователя по id."""
    user = await user_crud.get(user_id, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Данные не найдены',
        )
    await check_user_duplicate(user_update, session, user)
    check_user_contacts(user_update, user)
    check_password(user_update, user)
    check_admin_permission(user_update, current_user, user)
    return await user_crud.update(user, user_update, session)
