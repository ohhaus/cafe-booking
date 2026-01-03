import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.sessions import get_async_session
from src.media.schemas import ImageCreateResponse
from src.media.services import get_image_for_download, save_image
from src.users.dependencies import require_roles
from src.users.models import User, UserRole


router = APIRouter()
logger = logging.getLogger('app')


@router.post(
    '/',
    response_model=ImageCreateResponse,
    status_code=status.HTTP_201_CREATED,
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
async def download_image(
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> FileResponse:
    """Получить изображение по ID.

    Доступно всем, если изображение активно.
    """
    image_data = await get_image_for_download(session, image_id)

    return FileResponse(
        path=image_data.storage_path,
        media_type=image_data.mime_type or 'image/jpeg',
        filename=image_data.original_filename or f'{image_id}.jpg',
    )
