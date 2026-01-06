import logging

from sqlalchemy import select

from src.config import settings
from src.database.sessions import AsyncSessionLocal
from src.users.models import User, UserRole
from src.users.schemas import AdminUserCreate
from src.users.security import get_password_hash


logger = logging.getLogger('app')


async def create_superuser() -> None:
    """Создает суперпользователя если он не существует."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User).where(
                    (User.email == settings.superuser.EMAIL)
                    | (User.username == settings.superuser.USERNAME),
                ),
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                logger.info(
                    f'Суперпользователь существует: {existing_user.username}',
                )
                return

            admin_data = AdminUserCreate(
                username=settings.superuser.USERNAME,
                email=settings.superuser.EMAIL,
                phone=settings.superuser.PHONE,
                password=settings.superuser.PASSWORD,
                tg_id=settings.superuser.TG_ID,
                role=UserRole.ADMIN,
            )

            user_data = admin_data.model_dump(exclude={'password'})
            user_data['hashed_password'] = get_password_hash(
                admin_data.password,
            )
            user_data['active'] = True

            superuser = User(**user_data)
            session.add(superuser)
            await session.commit()

            logger.info(f'Создан суперпользователь: {superuser.username}')

        except Exception as e:
            await session.rollback()
            logger.error(f'Ошибка создания суперпользователя: {e}')
            raise
        finally:
            await session.close()
