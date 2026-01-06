from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import AsyncIterator
from zoneinfo import ZoneInfo

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from celery import Task
from src.booking.enums import BookingStatus
from src.booking.models import Booking
from src.cafes.models import Cafe
from src.celery.asyncio_runner import run_async
from src.celery.celery_app import celery_app
from src.celery.service import NotificationServise
from src.config import settings
from src.database.sessions import get_async_session


logger = get_task_logger(__name__)


@asynccontextmanager
async def session_ctx() -> AsyncIterator[AsyncSession]:
    """Инициализируем фсинхронную сессию для тасок."""
    agen = get_async_session()
    session = await anext(agen)
    try:
        yield session
    finally:
        await session.close()
        await agen.aclose()


def _calc_target_date(target_date: str | None) -> date:
    """Если дату не передали — напоминаем про брони на завтра по TIMEZONE.

    target_date можно передать строкой 'YYYY-MM-DD' для ручного прогона.
    """
    if target_date:
        return date.fromisoformat(target_date)

    tz = ZoneInfo(settings.celery.TIMEZONE)
    now_local = datetime.now(tz)
    return (now_local + timedelta(days=1)).date()


async def _send_daily_booking_reminders_async(target_date: str | None) -> int:
    notification = NotificationServise()
    day = _calc_target_date(target_date)

    async with session_ctx() as session:
        stmt = (
            select(Booking)
            .where(
                Booking.booking_date == day,
                Booking.status.in_(
                    [BookingStatus.BOOKING, BookingStatus.ACTIVE],
                ),
            )
            .options(
                selectinload(Booking.user),
                selectinload(Booking.cafe).selectinload(Cafe.managers),
                selectinload(Booking.booking_table_slots),
            )
        )

        bookings = (await session.scalars(stmt)).all()

    by_user_email: dict[str, list[Booking]] = defaultdict(list)
    for b in bookings:
        if getattr(b.user, 'email', None):
            by_user_email[b.user.email].append(b)

    sent = 0
    for email, items in by_user_email.items():
        subject = f'Напоминание о бронированиях на {day.isoformat()}'
        lines = []
        for b in items:
            lines.append(
                f'<li><b>{b.cafe.name}</b> — гостей: '
                f'{b.guest_number}, бронь: {b.id}</li>',
            )

        body = f"""
        <html>
          <body>
            <h2>Ваши бронирования на {day.isoformat()}</h2>
            <ul>
              {''.join(lines)}
            </ul>
            <p>Если планы изменились — отмените бронь заранее.</p>
          </body>
        </html>
        """

        await notification.send_email([email], subject, body)
        sent += 1

    logger.info(
        'Daily reminders: day=%s, bookings=%d, emails=%d',
        day,
        len(bookings),
        sent,
    )
    return sent


@celery_app.task(
    bind=True,
    name='src.celery.tasks.daily_reminders.send_daily_reminders',
    retry_backoff=True,
    retry_kwargs={'max_retries': 5},
)
def send_daily_reminders(
    self: Task,
    target_date: str | None = None,
) -> int:
    """Ежедневные напоминания клиентам о бронированиях.

    Обычно запускается Celery Beat раз в день.
    """
    return run_async(_send_daily_booking_reminders_async(target_date))
