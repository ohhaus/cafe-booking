import io
import logging
import asyncio
from pathlib import Path
import uuid

from PIL import Image
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.client import cache
from src.cache.keys import key_media
from src.common.exceptions import NotFoundException
from src.config import MEDIA_DIR, settings
from src.media.crud import create_image, get_image_by_id
from src.media.models import ImageMedia
from src.media.schemas import ImageMediaSchema
from src.media.validators import validate_image_upload


logger = logging.getLogger('app')


async def save_image(
    session: AsyncSession,
    file: UploadFile,
    uploaded_by_id: uuid.UUID,
) -> ImageMedia:
    """Сохраняет загруженное изображение и кэширует метаданные."""
    raw_bytes = await validate_image_upload(file)
    pil_image = Image.open(io.BytesIO(raw_bytes)).convert('RGB')

    image_id = uuid.uuid4()
    filename = f'{image_id}.jpg'
    path: Path = MEDIA_DIR / filename
    await asyncio.to_thread(
        lambda: path.parent.mkdir(parents=True, exist_ok=True)
        )

    await asyncio.to_thread(lambda: pil_image.save(path, format='JPEG'))
    stat = await asyncio.to_thread(path.stat)
    size = stat.st_size

    image = await create_image(
        session,
        id=image_id,
        filename=filename,
        original_filename=file.filename,
        file_size=size,
        mime_type=file.content_type,
        storage_path=str(path),
        uploaded_by_id=uploaded_by_id,
    )

    schema = ImageMediaSchema.model_validate(image)
    await cache.set(
        key_media(image_id),
        schema.model_dump(mode='json'),
        ttl=settings.cache.TTL_MEDIA,
    )

    return image


async def get_image_for_download(
    session: AsyncSession,
    image_id: uuid.UUID,
) -> ImageMedia:
    """Получить изображение по ID с использованием кэша."""
    cached_data = await cache.get(key_media(image_id))

    if cached_data:
        # Валидируем и возвращаем через схему
        schema = ImageMediaSchema(**cached_data)
        if not schema.active:
            raise NotFoundException('Изображение не найдено.')
        return schema

    image = await get_image_by_id(session, image_id)

    if not image or not image.active:
        logger.warning(
            'Изображение %s не найдено или неактивно',
            image_id,
            extra={'media_id': str(image_id)},
        )
        raise NotFoundException('Изображение не найдено.')

    schema = ImageMediaSchema.model_validate(image)
    await cache.set(
        key_media(image_id),
        schema.model_dump(mode='json'),
        ttl=settings.cache.TTL_MEDIA,
    )

    return image
