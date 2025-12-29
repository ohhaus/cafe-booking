# service.py
import io
import logging
import uuid

from PIL import Image
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.decorators import cached
from src.config import MEDIA_DIR
from src.media.crud import create_image, get_image_by_id
from src.media.models import ImageMedia
from src.media.schemas import ImageCacheSchema
from src.media.validators import validate_image_upload


logger = logging.getLogger('app')


async def save_image(
    session: AsyncSession,
    file: UploadFile,
    uploaded_by_id: uuid.UUID,
) -> ImageMedia:
    """Валидация, сохранение файла на диск и создание записи Image в БД."""
    raw_bytes = await validate_image_upload(file)
    pil_image: Image.Image = Image.open(io.BytesIO(raw_bytes))
    pil_image = pil_image.convert('RGB')

    image_id = uuid.uuid4()
    filename = f'{image_id}.jpg'
    path = MEDIA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    pil_image.save(path, format='JPEG')

    size = path.stat().st_size

    return await create_image(
        session,
        id=image_id,
        filename=filename,
        original_filename=file.filename,
        file_size=size,
        mime_type=file.content_type,
        storage_path=str(path),
        uploaded_by_id=uploaded_by_id,
    )


@cached('MEDIA')
async def get_image_for_download(
    session: AsyncSession,
    image_id: uuid.UUID,
) -> ImageCacheSchema:
    """Получение изображения для скачивания с валидацией и кэшированием."""
    image = await get_image_by_id(session, image_id)
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

    return ImageCacheSchema.model_validate(image)
