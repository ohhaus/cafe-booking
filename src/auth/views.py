from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.responces import LOGIN_RESPONSES
from src.config import settings
from src.database.sessions import get_async_session
from src.users.schemas import LoginForm, Token
from src.users.security import create_access_token, verify_password
from src.users.services import user_crud


router = APIRouter(
    prefix='/auth',
    tags=['Aутентификация'],
)


@router.post(
    '/auth/login',
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary='Получение токена авторизации',
    description='Возвращает токен для последующей авторизации пользователя.',
    responses=LOGIN_RESPONSES,
)
async def login(
        auth_data: LoginForm,
        session: AsyncSession = Depends(get_async_session),
        ) -> Token:
    """Возвращает токен для последующей авторизации пользователя."""
    user = await user_crud.get_by_username(auth_data.login, session)

    if not user or not verify_password(auth_data.password,
                                       user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Неверные имя пользователя или пароль',
        )

    expires_delta = timedelta(
        minutes=settings.auth.access_token_expire_minutes,
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=expires_delta,
        )

    return Token(access_token=access_token, token_type="bearer")
