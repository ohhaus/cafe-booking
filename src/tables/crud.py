from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from src.cafes.models import Cafe
from src.database.service import DatabaseService
from src.tables.models import Table
from src.tables.schemas import TableCreate, TableCreateDB, TableUpdate
from src.users.models import User


class TableService(DatabaseService[Table, dict, TableUpdate]):
    """Сервис для работы со столами в рамках кафе.

    Класс расширяет базовый DatabaseService и добавляет доменную логику:
    - ограничение доступа (только staff может создавать/обновлять);
    - правила видимости (user видит только активные записи и только в
    активном кафе);
    - привязку сущности к конкретному кафе через cafe_id;
    - маппинг полей API -> модель (
        seat_number -> count_place,
        is_active -> active
    ).
    """

    def __init__(self) -> None:
        """Инициализирует сервис и привязывает его к модели Table."""
        super().__init__(Table)

    # ----- HELPERS -----
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
        """Возвращает запрос стола к определенному кафе."""
        return (
            select(Table)
            .options(
                selectinload(Table.cafe),
            )
            .where(Table.cafe_id == cafe_id)
        )

    @staticmethod
    def _with_id(stmt: Select, table_id: UUID) -> Select:
        """Возвращает запрос определенного стола по ID."""
        return stmt.where(Table.id == table_id)

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
                return stmt.where(Table.active.is_(True))
            return stmt

        return (
            stmt.where(Table.active.is_(True))
            .join(Cafe, Cafe.id == Table.cafe_id)
            .where(Cafe.active.is_(True))
        )

    async def list_tables(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        show_all: bool = False,
    ) -> Sequence[Table]:
        """Возвращает список столов кафе с учётом прав доступа.

        Правила:
            - Staff-пользователь:
                * show_all=True  -> возвращает все столы кафе.
                * show_all=False -> возвращает только активные столы.
            - Обычный пользователь:
                * возвращает только активные столы.
                * только если кафе активно (иначе вернёт пустой результат).
        """
        stmt = self._cafe_scoped_stmt(
            cafe_id,
        ).order_by(Table.created_at.desc())
        stmt = self._apply_visibility_filters(
            stmt,
            current_user,
            show_all=show_all,
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_table(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        table_id: UUID,
    ) -> Optional[Table]:
        """Возвращает стол по UUID в рамках кафе с учётом правил видимости.

        Для обычного пользователя применяется фильтрация по активности стола
        и активности кафе. Для staff-ролей возвращается запись независимо от
        активности (если запись существует в рамках cafe_id).
        """
        stmt = self._cafe_scoped_stmt(cafe_id)
        stmt = self._with_id(stmt, table_id)
        stmt = self._apply_visibility_filters(stmt, current_user)

        result = await session.execute(stmt)
        return result.scalars().first()

    async def create_table(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        data: TableCreate,
    ) -> Table:
        """Создаёт стол в указанном кафе.

        Доступно только staff-пользователям. Перед созданием проверяет,
        что кафе существует.
        Также устанавливает cafe_id для создаваемой записи.
        """
        self._require_staff(
            current_user,
            'Недостаточно прав для создания стола',
        )

        cafe = await self._get_cafe_or_none(session, cafe_id)
        if not cafe:
            raise LookupError('Кафе не найдено')

        payload = data.model_dump()
        payload['cafe_id'] = cafe_id

        table_db = TableCreateDB(**payload)

        return await super().create(session, obj_in=table_db, commit=True)

    async def update_table(
        self,
        session: AsyncSession,
        current_user: User,
        cafe_id: UUID,
        table_id: UUID,
        data: TableUpdate,
    ) -> Optional[Table]:
        """Частично обновляет стол в рамках кафе.

        Доступно только staff-пользователям. Обновление выполняется только для
        записи, которая принадлежит указанному cafe_id.
        """
        self._require_staff(
            current_user,
            'Недостаточно прав для обновления стола',
        )

        table = await self.get_table(
            session,
            current_user=current_user,
            cafe_id=cafe_id,
            table_id=table_id,
        )

        if not table:
            return None

        payload = data.model_dump(exclude_unset=True)

        return await super().update(
            session,
            db_obj=table,
            obj_in=payload,
            commit=True,
        )
