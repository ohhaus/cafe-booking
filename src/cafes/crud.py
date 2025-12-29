from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from src.cafes.models import Cafe
from src.cafes.schemas import CafeCreate, CafeCreateDB, CafeUpdate
from src.cafes.service import sync_cafe_managers
from src.database.service import DatabaseService


class CafeService(DatabaseService[Cafe, CafeCreateDB, CafeUpdate]):
    """Сервис для работы с кафе.

    Класс расширяет базовый DatabaseService и добавляет доменную логику,
    связанную с назначением менеджеров кафе при создании и обновлении.

    Note:
        Операции create/update выполняются в рамках одной транзакции:
        сначала создаётся/обновляется Cafe без commit, затем синхронизируются
        менеджеры, после чего выполняются commit и refresh.

    """

    def __init__(self) -> None:
        """Инициализирует сервис и привязывает его к модели Cafe."""
        super().__init__(Cafe)

    def _stmt_with_managers(self) -> Select[tuple[Cafe]]:
        """Строит SELECT для кафе с предзагрузкой менеджеров."""
        return select(Cafe).options(selectinload(Cafe.managers))

    async def _get_with_managers_by_id(
        self,
        session: AsyncSession,
        cafe_id: UUID,
    ) -> Optional[Cafe]:
        """Получает кафе по ID вместе со списком менеджеров.

        Возвращает None, если кафе не найдено.
        """
        result = await session.execute(
            self._stmt_with_managers().where(
                Cafe.id == cafe_id,
            ),
        )
        return result.scalars().one_or_none()

    async def create_cafe(
        self,
        session: AsyncSession,
        cafe_in: CafeCreate,
    ) -> Cafe:
        """Создаёт кафе и синхронизирует список менеджеров."""
        managers_ids = cafe_in.managers_id

        payload = cafe_in.model_dump(exclude={'managers_id'})
        if payload.get('phone') is not None:
            payload['phone'] = str(payload['phone'])

        cafe_db = CafeCreateDB(**payload)

        cafe = await super().create(session, obj_in=cafe_db, commit=False)
        await session.flush()

        if managers_ids:
            await sync_cafe_managers(session, cafe, managers_ids)

        await session.commit()

        cafe_full = await self._get_with_managers_by_id(session, cafe.id)

        if cafe_full is None:
            raise RuntimeError(
                'Не удалось получить созданное кафе после commit',
            )
        return cafe_full

    async def update_cafe(
        self,
        session: AsyncSession,
        cafe: Cafe,
        cafe_in: CafeUpdate,
    ) -> Cafe:
        """Обновляет кафе и при необходимости синхронизирует менеджеров."""
        payload = cafe_in.model_dump(exclude_unset=True)

        managers_ids = payload.pop('managers_id', None)

        if 'phone' in payload and payload['phone'] is not None:
            payload['phone'] = str(payload['phone'])

        cafe = await super().update(
            session,
            db_obj=cafe,
            obj_in=payload,
            commit=False,
        )

        if managers_ids is not None:
            await sync_cafe_managers(session, cafe, managers_ids)

        await session.commit()
        cafe_full = await self._get_with_managers_by_id(session, cafe.id)
        if cafe_full is None:
            raise RuntimeError('Не удалось получить кафе после обновления')
        return cafe_full

    async def get_list_cafe(
        self,
        session: AsyncSession,
        *,
        include_inactive: bool,
    ) -> list[Cafe]:
        """Получение списка кафе."""
        stmt = self._stmt_with_managers()
        if not include_inactive:
            stmt = stmt.where(Cafe.active.is_(True))

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_cafe_by_id(
        self,
        session: AsyncSession,
        *,
        cafe_id: UUID,
        include_inactive: bool,
    ) -> Optional[Cafe]:
        """Получение кафе по его ID."""
        stmt = self._stmt_with_managers().where(Cafe.id == cafe_id)
        if not include_inactive:
            stmt = stmt.where(Cafe.active.is_(True))

        result = await session.execute(stmt)
        return result.scalars().first()


cafe_crud = CafeService()
