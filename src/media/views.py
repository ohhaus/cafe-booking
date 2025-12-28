import logging
from typing import cast
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache import cache
from src.cache.keys import key_media
from src.config import settings
from src.database.sessions import get_async_session
from src.media.crud import get_image
from src.media.schemas import ImageCreateResponse
from src.media.services import save_image
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()
logger = logging.getLogger('app')


@router.post(
    '/',
    response_model=ImageCreateResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_image(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.ADMIN, UserRole.MANAGER],
            allow_guest=False,
            only_active=True,
        ),
    ),
) -> ImageCreateResponse:
    """Загрузить изображение. Только для админа и менеджера."""
    try:
        image = await save_image(
            session=session,
            file=file,
            uploaded_by_id=current_user.id,
        )

        logger.info(
            'Изображение %s успешно загружено',
            image.id,
            extra={'user_id': str(current_user.id), 'media_id': str(image.id)},
        )

        return ImageCreateResponse(media_id=image.id)

    except Exception as e:
        logger.error(
            'Ошибка при загрузке изображения: %s',
            str(e),
            extra={'user_id': str(current_user.id), 'filename': file.filename},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Ошибка при загрузке изображения.',
        ) from e


@router.get('/{image_id}')
async def get_image_file(
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> FileResponse:
    """Получить файл изображения в бинарном виде.

    Кэширует metadata изображения (путь, mime_type, filename) на 60 минут,
    чтобы не делать запрос в БД при каждом обращении.
    """
    cache_key = key_media(image_id)
    cached_data = await cache.get(cache_key)

    if cached_data:
        logger.info(f'✓ Cache HIT: media {image_id}')
        return FileResponse(
            path=cached_data['path'],
            media_type=cached_data['mime_type'],
            filename=cached_data['filename'],
        )

    logger.debug(f'✗ Cache MISS: media {image_id}')
    image = await get_image(session, image_id)

    if not image or not image.active:
        logger.warning(
            'Изображение %s не найдено или неактивно',
            image_id,
            extra={'media_id': str(image_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено.',
        )

    metadata = {
        'path': image.storage_path,
        'mime_type': cast(str, image.mime_type),
        'filename': cast(str, image.original_filename),
    }
    await cache.set(cache_key, metadata, ttl=settings.cache.TTL_MEDIA)

    return FileResponse(
        path=image.storage_path,
        media_type=cast(str, image.mime_type),
        filename=cast(str, image.original_filename),
    )
