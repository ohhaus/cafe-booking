from typing import Optional
from urllib.parse import urlparse, urlunparse


def build_redis_url(
    base_url: str,
    password: Optional[str],
    db: int,
) -> str:
    """Фабрика URL с паролем для подключения Celery к Redis."""
    url = urlparse(base_url)
    scheme = url.scheme or 'redis'
    host = url.hostname or 'localhost'
    port = url.port or 6379

    if password:
        netloc = f':{password}@{host}:{port}'
    else:
        netloc = f'{host}:{port}'

    path = f'/{db}'
    return urlunparse((scheme, netloc, path, '', '', ''))
