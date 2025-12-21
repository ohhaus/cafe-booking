import io
import uuid

from PIL import Image
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import MEDIA_DIR
from src.media.crud import create_image
from src.media.models import ImageMedia
from src.media.validators import validate_image_upload


async def save_image(
    session: AsyncSession,
    file: UploadFile,
    uploaded_by_id: uuid.UUID,
) -> ImageMedia:
    """Валидация, сохранение файла на диск и создание записи Image в БД."""
    await validate_image_upload
    raw_bytes = await file.read()

    pil_image: Image.Image = Image.open(io.BytesIO(raw_bytes))
    pil_image = pil_image.convert("RGB")

    image_id = uuid.uuid4()
    filename = f"{image_id}.jpg"
    path = MEDIA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    pil_image.save(path, format="JPEG")

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
