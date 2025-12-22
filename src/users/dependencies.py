from typing import Awaitable, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.common.logging import log_action
from src.config import settings
from src.database.sessions import get_async_session
from src.users.models import User, UserRole


security = HTTPBearer(auto_error=False)

SECRET_KEY = settings.auth.secret_key
ALGORITHM = settings.auth.algorithm


def require_roles(
    allowed_roles: list[UserRole] | None = None,
    allow_guest: bool = False,
    only_active: bool = True,
) -> Callable[..., Awaitable[User | None]]:
    """Проверяет права доступа пользователя."""

    @log_action('Проверка прав доступа пользователя.', skip_logging=True)
    async def dependency(
        session: AsyncSession = Depends(get_async_session),
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> User | None:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Неавторизированный пользователь',
            headers={'WWW-Authenticate': 'Bearer'},
        )

        if not credentials:
            if allow_guest:
                return None
            raise credentials_exception

        token = credentials.credentials

        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
            )
            user_id_str: str | None = payload.get('sub')
            if not user_id_str:
                raise credentials_exception

            try:
                user_id = UUID(user_id_str)
            except (ValueError, AttributeError, TypeError):
                raise credentials_exception

        except PyJWTError:
            raise credentials_exception

        result = await session.execute(
            select(User).where(User.id == user_id),
        )
        user: User | None = result.scalar_one_or_none()
        if not user:
            raise credentials_exception

        if only_active and not user.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Пользователь не активен. Обратитесь к администрации',
            )
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Доступ запрещен',
            )
        return user

    return dependency
