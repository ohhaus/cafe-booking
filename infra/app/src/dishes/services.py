# src/dishes/services.py

import logging
from typing import List, Optional
from uuid import UUID

from asyncpg.exceptions import UniqueViolationError
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.models import Cafe
from src.common.exceptions import NotFoundException, ValidationErrorException
from src.database.service import DatabaseService, unwrap_sa_integrity_error
from src.dishes.crud import dishes_crud
from src.dishes.models import Dish, dish_cafe
from src.dishes.schemas import DishCreate, DishInfo, DishUpdate
from src.dishes.validators import check_exists_dish, validate_active_cafes_ids
from src.users.models import User, UserRole


logger = logging.getLogger('app')


class DishService(DatabaseService[Dish, DishCreate, DishUpdate]):
    """Сервис для работы с блюдами."""

    async def create_dish_service(
        self,
        session: AsyncSession,
        dish_in: DishCreate,
        current_user: User,
    ) -> Dish:
        """Создание нового блюда.

        Если указаны cafes_id, связывает блюдо с кафе.
        """
        user_id = str(current_user.id)
        dish_name = dish_in.name

        logger.info(
            'Пользователь %s инициировал создание блюда %s',
            user_id,
            dish_name,
            extra={'user_id': user_id, 'dish_name': dish_name},
        )

        data = dish_in.model_dump(exclude_unset=True)
        cafes_ids = data.pop('cafes_id', None)

        if cafes_ids:
            cafes_ids = list(dict.fromkeys(cafes_ids))

        db_obj = Dish(**data)

        try:
            if cafes_ids:
                try:
                    cafes = await validate_active_cafes_ids(
                        session=session,
                        cafes_ids=cafes_ids,
                    )
                except NotFoundException:
                    logger.warning(
                        'Часть ID Кафе не найдено или не активны',
                        extra={
                            'user_id': user_id,
                            'dish_name': dish_name,
                            'missing_cafes_ids': [str(x) for x in cafes_ids],
                        },
                    )
                    raise

                db_obj.cafes = cafes

            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj, attribute_names=['cafes'])
            logger.info(
                'Создание блюда %s успешно завершено',
                dish_name,
                extra={
                    'user_id': user_id,
                    'dish_id': str(db_obj.id),
                    'dish_name': dish_name,
                },
            )
            return db_obj

        except (NotFoundException, ValidationErrorException):
            await session.rollback()
            raise

        except IntegrityError as e:
            await session.rollback()
            cause = unwrap_sa_integrity_error(e)
            if isinstance(cause, UniqueViolationError):
                # можно точнее: по constraint
                if getattr(cause, 'constraint_name', None) == 'dish_name_key':
                    raise ValidationErrorException(
                        f"Блюдо с именем '{dish_name}' уже существует",
                    ) from e
            raise

        except SQLAlchemyError:
            # любые ошибки SQLAlchemy/БД
            await session.rollback()
            logger.exception(
                'Создание блюда упало с ошибкой БД',
                extra={'user_id': user_id, 'dish_name': dish_name},
            )
            raise

        except Exception:
            # реально неожиданное
            await session.rollback()
            logger.exception(
                'Создание блюда упало с необработанной ошибкой',
                extra={'user_id': user_id, 'dish_name': dish_name},
            )
            raise

    async def update_dish_service(
        self,
        *,
        session: AsyncSession,
        dish_id: UUID,
        dish_update: DishUpdate,
        current_user: User,
    ) -> Dish:
        """Обновление информации о блюде по его ID.

        Если указаны cafes_id, обновляет связь блюда с кафе.
        """
        user_id = str(current_user.id)

        logger.info(
            'Пользователь %s инициировал обновление блюда %s',
            user_id,
            str(dish_id),
            extra={'user_id': user_id, 'dish_id': str(dish_id)},
        )

        dish = await dishes_crud.get_by_id_with_cafes(
            session=session,
            dish_id=dish_id,
        )
        if dish is None:
            logger.warning(
                'Блюдо не найдено',
                extra={'user_id': user_id, 'dish_id': str(dish_id)},
            )
            raise NotFoundException(f'Блюдо с ID: {dish_id} не найдено')

        data = dish_update.model_dump(exclude_unset=True)
        cafes_ids = data.pop('cafes_id', None)

        if cafes_ids:
            cafes_ids = list(dict.fromkeys(cafes_ids))

        try:
            if cafes_ids:
                try:
                    cafes = await validate_active_cafes_ids(
                        session=session,
                        cafes_ids=cafes_ids,
                    )
                except NotFoundException:
                    logger.warning(
                        'Часть ID Кафе не найдено или не активны '
                        'при обновлении блюда',
                        extra={
                            'user_id': user_id,
                            'dish_id': str(dish_id),
                            'missing_cafes_ids': [str(x) for x in cafes_ids],
                        },
                    )
                    await session.rollback()
                    raise
                dish.cafes = cafes
            else:
                # пришёл пустой список — очищаем связь
                logger.warning(
                    'Нельзя обновить блюдо %s с пустым списком кафе',
                    str(dish_id),
                    extra={
                        'user_id': user_id,
                        'dish_id': str(dish_id),
                        'missing_cafes_ids': [str(x) for x in cafes_ids],
                    },
                )
                await session.rollback()
                raise ValidationErrorException(
                    'Список кафе для блюда не может быть пустым',
                )
            dish = await dishes_crud.update_dish(
                session=session,
                dish=dish,
                data=data,
            )
        except IntegrityError as e:
            await session.rollback()
            cause = unwrap_sa_integrity_error(e)
            if isinstance(cause, UniqueViolationError):
                if getattr(cause, 'constraint_name', None) == 'dish_name_key':
                    name = data.get('name')
                    raise ValidationErrorException(
                        f"Блюдо с именем '{name}' уже существует",
                    ) from e
            raise
        except SQLAlchemyError:
            await session.rollback()
            logger.exception(
                'SQLAlchemy ошибка при обновлении блюда',
                extra={'user_id': user_id, 'dish_id': str(dish_id)},
            )
            raise
        except Exception:
            # реально неожиданное
            await session.rollback()
            logger.exception(
                'Обновление блюда упало с необработанной ошибкой',
                extra={'user_id': user_id, 'dish_id': str(dish_id)},
            )
            raise

        return dish

    async def get_cafes_for_dish(
        self,
        session: AsyncSession,
        dish_id: UUID,
    ) -> List[Cafe]:
        """Получает связанные активные кафе для данного блюда.

        Args:
            session: Сессия БД
            dish_id: UUID блюда

        Returns:
            Список объектов Cafe

        Raises:
            NotFoundException: Если блюдо не найдено

        """
        # Сначала проверяем, что блюдо существует
        await check_exists_dish(dish_id, session)

        # Получаем кафе через таблицу связи
        query = (
            select(Cafe)
            .join(dish_cafe)
            .where(
                dish_cafe.c.dish_id == dish_id,
                Cafe.active.is_(True),
            )
        )
        result = await session.execute(query)
        return result.scalars().all()


async def get_dishes(
    session: AsyncSession,
    current_user: User,
    show_all: bool = False,
    cafe_id: Optional[UUID] = None,
) -> List[DishInfo]:
    """Получение списка блюд с фильтрацией по Кафе и Статусу активности.

    - Для обычных пользователей: только активные блюда.
    - Для Админов и Менеджеров: можно фильтровать по активности.
    - show_all: показывать только активные (по умолчанию) или все.
    """
    logger.info(
        'Пользователь %s запросил все блюда с фильтрами: '
        'show_all=%s, cafe_id=%s',
        current_user.id,
        show_all,
        cafe_id,
        extra={'user_id': str(current_user.id)},
    )

    filters = []

    if not current_user.is_staff():
        show_all = False

    if cafe_id is not None:
        filters.append(Dish.cafes.any(Cafe.id == cafe_id))
    if not show_all:
        filters.append(Dish.active.is_(True))

    dishes = await dishes_crud.get_multi(
        session=session,
        filters=filters,
        relationships=['cafes'],
        order_by=[desc(Dish.created_at)],
    )

    found_count = len(dishes)

    logger.info(
        'Найдено блюд: %d (show_all=%s, cafe_id=%s)',
        found_count,
        show_all,
        cafe_id,
        extra={
            'found_count': found_count,
            'show_all': show_all,
            'cafe_id': str(cafe_id) if cafe_id else None,
        },
    )

    if found_count == 0:
        return []

    try:
        result = [
            DishInfo.model_validate(d, from_attributes=True) for d in dishes
        ]

        logger.info(
            'Пользователю %s возвращено блюд: %d',
            current_user.id,
            len(result),
            extra={
                'user_id': str(current_user.id),
                'returned_count': len(result),
            },
        )
        return result

    except ValidationError:
        logger.error(
            'Ошибка валидации данных блюд',
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise ValidationErrorException('Ошибка валидации данных блюда')


async def get_dish_by_dish_id(
    session: AsyncSession,
    dish_id: UUID,
    current_user: User,
) -> Dish:
    """Получает Блюдо по ID с учётом прав доступа."""
    logger.info(
        'Пользователь c ID: %s запросил информацию о блюде с ID: %s',
        current_user.id,
        dish_id,
        extra={'user_id': str(current_user.id)},
    )

    # Определяем, может ли пользователь видеть все блюда
    can_view_all = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)

    # Формируем фильтры
    filters = [Dish.id == dish_id]
    if not can_view_all:
        filters.append(Dish.active.is_(True))

    # Получаем блюдо из БД
    dishes = await dishes_crud.get_multi(
        session=session,
        filters=filters,
        relationships=['cafes'],
    )

    dish = dishes[0] if dishes else None

    if dish is None:
        logger.warning(
            'Блюдо с ID: %s не найдено для пользователя %s',
            dish_id,
            current_user.id,
            extra={'user_id': str(current_user.id)},
        )
        raise NotFoundException(message='Блюдо не найдено')

    try:
        validate_dish = DishInfo.model_validate(dish, from_attributes=True)

        logger.info(
            'Блюдо с ID: %s успешно получено для пользователя %s',
            dish_id,
            current_user.id,
            extra={'user_id': str(current_user.id)},
        )

        return validate_dish

    except ValidationError:
        logger.error(
            'Ошибка валидации данных блюда',
            extra={'user_id': str(current_user.id)},
            exc_info=True,
        )
        raise ValidationErrorException(
            'Ошибка валидации данных блюда',
        )


dishes_service = DishService(Dish)
