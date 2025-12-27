from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.auth.responses import LOGIN_RESPONSES
from src.config import settings
from src.database.sessions import get_async_session
from src.users.models import User
from src.users.schemas import AuthData, AuthToken
from src.users.security import create_access_token, verify_password


router = APIRouter()


@router.post(
    '/login',
    response_model=AuthToken,
    status_code=status.HTTP_200_OK,
    summary='Получение токена авторизации',
    description='Возвращает токен для последующей авторизации пользователя.',
    responses=LOGIN_RESPONSES,
)
async def login(
    auth_data: AuthData,
    session: AsyncSession = Depends(get_async_session),
) -> AuthToken:
    """Возвращает токен для последующей авторизации пользователя."""
    stmt = select(User).where(
        or_(
            User.email == auth_data.login,
            User.phone == auth_data.login,
        ),
    )
    result = await session.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(
        auth_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Неверные имя пользователя или пароль',
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Пользователь не активен',
        )

    expires_delta = timedelta(
        minutes=settings.auth.access_token_expire_minutes,
    )

    access_token = create_access_token(
        data={'sub': str(user.id)},
        expires_delta=expires_delta,
    )

    return AuthToken(access_token=access_token, token_type='bearer')
