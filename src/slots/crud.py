from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from src.cafes.models import Cafe
from src.database.service import DatabaseService
from src.slots.models import Slot
from src.slots.schemas import TimeSlotCreate, TimeSlotCreateDB, TimeSlotUpdate
from src.users.models import User


class SlotService(DatabaseService[Slot, TimeSlotCreateDB, TimeSlotUpdate]):
    """Сервис для работы со слотами в рамках кафе.

    Класс расширяет базовый DatabaseService и добавляет доменную логику:
    - ограничение доступа (только staff может создавать/обновлять слоты);
    - правила видимости (user видит только активные слоты и только в
    активном кафе);
    - привязку слота к конкретному кафе через cafe_id;
    - маппинг полей API -> модель (is_active -> active);
    - проверку валидности временного интервала при обновлении
    (start_time < end_time).
    """

    def __init__(self) -> None:
        """Инициализирует сервис и привязывает его к модели Slot."""
        super().__init__(Slot)

    #  -----HELPERS-----
    @staticmethod
    def _require_staff(
        user: User,
        message: str,
    ) -> None:
        """Хелпер, проверяет пользователя на то что он сотрудник."""
        if not user.is_staff():
            raise PermissionError(message)

    @staticmethod
    async def _get_cafe_or_none(
        db: AsyncSession,
        cafe_id: UUID,
    ) -> Optional[Cafe]:
        """Возвращает кафе по ID."""
        result = await db.execute(select(Cafe).where(Cafe.id == cafe_id))
        return result.scalars().first()

    @staticmethod
    def _cafe_scoped_stmt(cafe_id: UUID) -> Select:
        """Возвращает запрос слота к определенному кафе."""
        return (
            select(Slot)
            .options(selectinload(Slot.cafe))
            .where(Slot.cafe_id == cafe_id)
        )

    @staticmethod
    def _with_id(stmt: Select, slot_id: UUID) -> Select:
        """Возвращает запрос определенного слота по ID."""
        return stmt.where(Slot.id == slot_id)

    @staticmethod
    def _apply_visibility_filters(
        stmt: Select,
        current_user: User,
        *,
        show_all: Optional[bool] = None,
    ) -> Select:
        """Правила.

        - staff:
            show_all=False -> только активные.
            show_all=True/None -> все.
        - user:
            только активные,
            и только если Cafe.active=True.
        """
        if current_user.is_staff():
            if show_all is False:
                return stmt.where(Slot.active.is_(True))
            return stmt

        return (
            stmt.where(Slot.active.is_(True))
            .join(Cafe, Cafe.id == Slot.cafe_id)
            .where(Cafe.active.is_(True))
        )

    async def list_slots(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        show_all: bool = False,
    ) -> Sequence[Slot]:
        """Возвращает список слотов кафе с учётом прав доступа."""
        stmt = self._cafe_scoped_stmt(cafe_id).order_by(Slot.start_time)
        stmt = self._apply_visibility_filters(
            stmt,
            current_user,
            show_all=show_all,
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_slot(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        slot_id: UUID,
    ) -> Optional[Slot]:
        """Возвращает слот по UUID в рамках кафе с учётом правил видимости.

        Для обычного пользователя применяется фильтрация по активности слота
        и активности кафе. Для staff-ролей возвращается запись независимо от
        активности (если запись существует в рамках cafe_id).
        """
        stmt = self._cafe_scoped_stmt(cafe_id)
        stmt = self._with_id(stmt, slot_id)
        stmt = self._apply_visibility_filters(stmt, current_user)

        result = await session.execute(stmt)
        return result.scalars().first()

    async def create_slot(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        data: TimeSlotCreate,
    ) -> Slot:
        """Создаёт слот в указанном кафе.

        Доступно только staff-пользователям. Перед созданием проверяет,
        что кафе существует. Слот создаётся с привязкой к cafe_id.
        """
        self._require_staff(
            current_user,
            'Недостаточно прав для создания слота',
        )

        cafe = await self._get_cafe_or_none(session, cafe_id)
        if not cafe:
            raise LookupError('Кафе не найдено')

        slot_db = TimeSlotCreateDB(cafe_id=cafe_id, **data.model_dump())
        return await super().create(session, obj_in=slot_db, commit=True)

    async def update_slot(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        slot_id: UUID,
        data: TimeSlotUpdate,
    ) -> Optional[Slot]:
        """Частично обновляет слот в рамках кафе.

        Доступно только staff-пользователям. Обновление выполняется только для
        записи, которая принадлежит указанному cafe_id.

        Дополнительно защищает инвариант временного интервала:
            - итоговое start_time должно быть меньше end_time
              (учитывается частичное обновление, когда передано только одно
              поле)
        """
        self._require_staff(
            current_user,
            'Недостаточно прав для обновления слота',
        )

        slot = await self.get_slot(
            session,
            current_user=current_user,
            cafe_id=cafe_id,
            slot_id=slot_id,
        )
        if not slot:
            return None

        payload = data.model_dump(
            exclude_unset=True,
            by_alias=False,
        )

        new_start = payload.get('start_time', slot.start_time)
        new_end = payload.get('end_time', slot.end_time)
        if new_start >= new_end:
            raise ValueError('start_time должен быть меньше end_time')

        return await super().update(
            session,
            db_obj=slot,
            obj_in=payload,
            commit=True,
        )
