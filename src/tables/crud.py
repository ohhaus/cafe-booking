from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.cafes.cafe_scoped import (
    apply_visibility_filters,
    cafe_scoped_stmt,
    get_cafe_or_none,
    require_staff,
    with_id,
)
from src.database.service import DatabaseService
from src.tables.models import Table
from src.tables.schemas import TableCreate, TableCreateDB, TableUpdate
from src.users.models import User


class TableService(DatabaseService[Table, TableCreateDB, TableUpdate]):
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
        stmt = cafe_scoped_stmt(
            Table,
            cafe_id,
        ).order_by(Table.created_at.desc())
        stmt = apply_visibility_filters(
            Table,
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
        stmt = cafe_scoped_stmt(Table, cafe_id)
        stmt = with_id(Table, stmt, table_id)
        stmt = apply_visibility_filters(
            Table,
            stmt,
            current_user,
            show_all=True,
        )

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
        require_staff(
            current_user,
            'Недостаточно прав для создания стола',
        )

        cafe = await get_cafe_or_none(session, cafe_id)
        if not cafe:
            raise LookupError('Кафе не найдено')

        table_db = TableCreateDB(cafe_id=cafe_id, **data.model_dump())

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
        require_staff(
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

        payload = data.model_dump(
            exclude_unset=True,
            by_alias=False,
        )

        return await super().update(
            session,
            db_obj=table,
            obj_in=payload,
            commit=True,
        )
