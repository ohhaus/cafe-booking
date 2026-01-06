from datetime import datetime, timedelta, timezone

from jwt import encode
from pwdlib import PasswordHash

from src.config import settings


SECRET_KEY = settings.auth.SECRET_KEY
ALGORITHM = settings.auth.ALGORITHM
password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Верификация пароля."""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хеширование пароля."""
    return password_hash.hash(password)


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    """Создание JWT токена."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({'exp': expire})
    return encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
