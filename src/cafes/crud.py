from sqlalchemy.ext.asyncio import AsyncSession

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

    async def create_cafe(
        self,
        session: AsyncSession,
        cafe_in: CafeCreate,
    ) -> Cafe:
        """Создаёт кафе и синхронизирует список менеджеров.

        Алгоритм:
        1) Извлекает managers_id из входной схемы.
        2) Создаёт Cafe через базовый CRUD без commit.
        3) Делает flush, чтобы получить идентификатор созданного кафе.
        4) Если переданы managers_id — синхронизирует связи менеджеров.
        5) Выполняет commit и refresh и возвращает объект Cafe.
        """
        managers_ids = cafe_in.managers_id

        cafe_db = CafeCreateDB(**cafe_in.model_dump(exclude={'managers_id'}))

        cafe = await super().create(session, obj_in=cafe_db, commit=False)
        await session.flush()

        if managers_ids:
            await sync_cafe_managers(session, cafe, managers_ids)

        await session.commit()
        await session.refresh(cafe)
        return cafe

    async def update_cafe(
        self,
        session: AsyncSession,
        cafe: Cafe,
        cafe_in: CafeUpdate,
    ) -> Cafe:
        """Обновляет кафе и при необходимости синхронизирует менеджеров.

        Алгоритм:
          1) Собирает payload только из переданных полей (exclude_unset=True).
          2) Извлекает managers_id из payload (если ключ присутствует).
          3) Нормализует phone к строке, если значение задано.
          4) Обновляет Cafe через базовый CRUD без commit.
          5) Если managers_id был передан (даже пустым списком) —
             синхронизирует связи менеджеров.
          6) Выполняет commit и refresh и возвращает объект Cafe.
        """
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
        await session.refresh(cafe)
        return cafe
