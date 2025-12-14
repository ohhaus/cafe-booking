from fastapi import HTTPException, UploadFile, status

from src.config import (ALLOWED_IMAGE_MIME_TYPES, MAX_FILE_SIZE,
                        MAX_FILE_SIZE_MB)


async def validate_image_upload(file: UploadFile) -> bytes:
    """Валидация загружаемого изображения."""

    if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Неподдерживаемый тип файла. Доступны JPG и PNG.'
        )

    content = await file.read()
    size = len(content)

    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Файл пуст.'
        )

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f'Файл слишком большой. Максимум {MAX_FILE_SIZE_MB} МБ.'
        )
    return content
