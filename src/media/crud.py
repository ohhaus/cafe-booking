import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.media.models import Image


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
) -> Image:
    """Создаёт запись изображения в БД."""
    image = Image(
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


async def get_image(session: AsyncSession,
                    image_id: uuid.UUID) -> Image | None:
    """Возвращает изображение по ID или None, если не найдено."""
    return await session.get(Image, image_id)


async def list_images(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 50,
) -> list[Image]:
    """Возвращает список изображений с пагинацией."""
    stmt = select(Image).offset(skip).limit(limit)
    res = await session.execute(stmt)
    images: Sequence[Image] = res.scalars().all()
    return list(images)


async def soft_delete_image(db: AsyncSession, image: Image) -> None:
    """Мягко удаляет изображение (active = False)."""
    image.active = False
    await db.commit()
