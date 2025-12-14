import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import MEDIA_DIR
from src.media.crud import create_image
from src.media.models import Image
from src.media.validators import validate_image_upload


async def save_image(
    session: AsyncSession,
    file: UploadFile,
    uploaded_by_id: uuid.UUID,
) -> Image:
    """Валидация, сохранение файла на диск и создание записи Image в БД."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отсутствует имя файла.",
        )
    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отсутствует тип файла.",
        )

    content = await validate_image_upload(file)
    size = len(content)

    image_id = uuid.uuid4()
    filename = f"{image_id}.jpg"
    path: Path = MEDIA_DIR / filename
    path.write_bytes(content)

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
    return image
