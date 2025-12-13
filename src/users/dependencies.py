from typing import Awaitable, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pyJWT.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.config import settings
from src.database.sessions import get_async_session
from src.services.decorators import log_action
from src.users.models import User, UserRole


bearer_scheme = HTTPBearer(auto_error=False)

SECRET_KEY = settings.auth.secret_key
ALGORITHM = settings.auth.algorithm


def require_roles(
    allowed_roles: list[UserRole] | None = None,
    allow_guest: bool = False,
    only_active: bool = True,
) -> Callable[
    [AsyncSession, HTTPAuthorizationCredentials | None],
    Awaitable[User | None],
]:
    """Проверка прав доступа пользователя.

    Возвращает функцию-зависимость, которую можно использовать в Depends.
    """

    @log_action('Проверка прав доступа пользователя.', skip_logging=True)
    async def dependency(
        session: AsyncSession = Depends(get_async_session),
        credentials: HTTPAuthorizationCredentials | None = Depends(
            bearer_scheme,
        ),
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
        try:
            payload = jwt.decode(
                credentials.credentials,
                SECRET_KEY,
                algorithms=[ALGORITHM],
            )
            user_id: int | None = payload.get('sub')
            if not user_id:
                raise credentials_exception
        except InvalidTokenError:
            raise credentials_exception

        result = await session.execute(
            select(User).where(User.id == int(user_id)),
        )
        user: User | None = result.scalar_one_or_none()
        if not user:
            raise credentials_exception
        if only_active and not user.is_active:
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
