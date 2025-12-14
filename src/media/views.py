import uuid
from typing import cast

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.sessions import get_async_session
from src.media.crud import get_image, list_images, soft_delete_image
from src.media.models import Image
from src.media.schemas import ImageResponse
from src.media.services import save_image
from src.users.dependencies import require_roles
from src.users.models import User, UserRole

router = APIRouter(prefix='/media', tags=['media'])


@router.post(
    '/',
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_image(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.ADMIN, UserRole.MANAGER],
            allow_guest=False,
            only_active=True,
        )
    )
) -> Image:
    """Загрузить изображение. Только для админа и менеджера."""
    image = await save_image(
        session=session,
        file=file,
        uploaded_by_id=current_user.id
    )
    return image


@router.get(
    '/{image_id}',
    response_model=ImageResponse
)
async def get_image_info(
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
) -> Image:
    """Получить метаданные изображения по ID."""
    image = await get_image(session, image_id)
    if not image or not image.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено'
        )
    return image


@router.get('/{image_id}/file')
async def get_image_file(
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
) -> FileResponse:
    """Получить файл изображения в бинарном виде."""
    image = await get_image(session, image_id)
    if not image or not image.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено.'
        )
    return FileResponse(
        path=image.storage_path,
        media_type=cast(str, image.mime_type),
        filename=cast(str, image.original_filename)
    )


@router.get(
    "/",
    response_model=list[ImageResponse],
)
async def get_images_list(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_session),
) -> list[Image]:
    """Получить список активных изображений с пагинацией."""
    if limit > 100:
        limit = 100
    images = await list_images(db, skip=skip, limit=limit)
    return images


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_image(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(
        require_roles(
            allowed_roles=[UserRole.ADMIN, UserRole.MANAGER],
            allow_guest=False,
            only_active=True,
        )
    ),
) -> None:
    """Удалить изображение. Доступно только администратору и менеджеру."""
    image = await get_image(db, image_id)
    if not image or not image.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Изображение не найдено",
        )

    await soft_delete_image(db, image)
