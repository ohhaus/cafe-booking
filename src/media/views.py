from typing import cast
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.sessions import get_async_session
from src.media.crud import get_image
from src.media.schemas import ImageCreateResponse
from src.media.services import save_image
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()


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
    image = await save_image(
        session=session,
        file=file,
        uploaded_by_id=current_user.id,
    )
    return ImageCreateResponse(meida_id=image.id)


@router.get('/{image_id}')
async def get_image_file(
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> FileResponse:
    """Получить файл изображения в бинарном виде."""
    image = await get_image(session, image_id)
    if not image or not image.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено.',
        )
    return FileResponse(
        path=image.storage_path,
        media_type=cast(str, image.mime_type),
        filename=cast(str, image.original_filename),
    )
