from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from celery import Task
from src.booking.models import Booking
from src.cafes.models import Cafe
from src.celery.asyncio_runner import run_async
from src.celery.celery_app import celery_app
from src.celery.service import NotificationServise
from src.database.sessions import get_async_session


logger = get_task_logger(__name__)


@asynccontextmanager
async def session_cts() -> AsyncIterator[AsyncSession]:
    """Инициализируем фсинхронную сессию для тасок."""
    agen = get_async_session()
    session = await anext(agen)
    try:
        yield session
    finally:
        await session.close()
        await agen.aclose()


def _subject_body(
    event: str,
    payload: Optional[dict[str, Any]],
) -> tuple[str, str]:
    """Фабрика формирования писем для работы с бронирование."""
    payload = payload or {}

    templates = {
        'created': ('Новая бронь', 'Создано новое бронирование.'),
        'updated': ('Изменение брони', 'Бронирование было изменено.'),
        'canceled': ('Отмена брони', 'Бронирование было отменено.'),
        'activated': (
            'Бронь активирована',
            'Бронирование перешло в активный статус.',
        ),
        'restored': (
            'Бронь восстановлена',
            'Бронирование было восстановлено.',
        ),
    }
    subject, body = templates.get(
        event,
        (
            'Событие по брони',
            f'Событие: {event}',
        ),
    )
    extra = payload.get('message')
    if extra:
        body = f'{body}\n\n{extra}'

    return subject, body


async def _notify_admins_about_event_async(
    booking_id: str,
    event: str,
    payload: Optional[dict[str, Any]],
) -> None:
    """Получаем администраторов для рассылки."""
    notification = NotificationServise()
    subject, body = _subject_body(event, payload)

    async with session_cts() as session:
        stmt = (
            select(Booking)
            .where(Booking.id == UUID(booking_id))
            .options(
                selectinload(Booking.user),
                selectinload(Booking.cafe).selectinload(Cafe.managers),
                selectinload(Booking.booking_table_slots),
            )
        )
        booking = await session.scalar(stmt)

        if not booking:
            logger.warning('Booking %s not found, skip notify', booking_id)
            return

        await notification.notify_managers_and_admins(
            booking=booking,
            subject=subject,
            body=body,
        )


@celery_app.task(
    bind=True,
    name='src.celery.tasks.admin_events.notify_admins_about_event',
    retry_backoff=True,
    retry_kwargs={'max_retries': 5},
)
def notify_admins_about_event(
    self: Task,
    booking_id: str,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Массовая рассылка администраторам/менеджерам по событию.

    Вызывай из кода после успешного commit брони:
      notify_admins_about_event.delay(str(booking.id), "created")
    """
    run_async(
        _notify_admins_about_event_async(
            booking_id,
            event,
            payload,
        ),
    )
