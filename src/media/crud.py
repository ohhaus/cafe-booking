import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.media.models import ImageMedia


async def create_image(
    session: AsyncSession,
    *,
    id: uuid.UUID,
    filename: str,
    original_filename: str,
    file_size: int,
    mime_type: str,
    storage_path: str,
    uploaded_by_id: uuid.UUID,
) -> ImageMedia:
    """Создаёт запись изображения в БД."""
    image = ImageMedia(
        id=id,
        filename=filename,
        original_filename=original_filename,
        file_size=file_size,
        mime_type=mime_type,
        storage_path=storage_path,
        uploaded_by_id=uploaded_by_id,
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


async def get_image_by_id(
    session: AsyncSession,
    image_id: uuid.UUID,
) -> ImageMedia | None:
    """Возвращает изображение по ID или None, если не найдено."""
    return await session.get(ImageMedia, image_id)
