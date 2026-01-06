from celery.schedules import crontab

from celery import Celery
from src.celery.utils import build_redis_url
from src.config import settings
import src.database.models_imports  # noqa: F401


celery_app = Celery('app')

broker_url = build_redis_url(
    settings.redis.URL,
    settings.redis.PASSWORD,
    settings.celery.BROKER_DB,
)
result_backend = build_redis_url(
    settings.redis.URL,
    settings.redis.PASSWORD,
    settings.celery.RESULT_DB,
)

celery_app.conf.update(
    broker_url=broker_url,
    result_backend=(
        None if settings.celery.TASK_IGNORE_RESULT else result_backend
    ),
    task_serializer=settings.celery.TASK_SERIALIZER,
    result_serializer=settings.celery.RESULT_SERIALIZER,
    accept_content=settings.celery.ACCEPT_CONTENT,
    timezone=settings.celery.TIMEZONE,
    enable_utc=settings.celery.ENABLE_UTC,
    task_ignore_result=settings.celery.TASK_IGNORE_RESULT,
    task_track_started=settings.celery.TASK_TRACK_STARTED,
    broker_connection_retry_on_startup=(
        settings.celery.BROKER_CONNECTION_RETRY_ON_STARTUP
    ),
    task_time_limit=settings.celery.TASK_TIME_LIMIT,
    task_soft_time_limit=settings.celery.TASK_SOFT_TIME_LIMIT,
    worker_send_task_events=True,
    task_send_sent_event=True,
    worker_enable_remote_control=True,
    broker_transport_options=settings.celery.BROKER_TRANSPORT_OPTIONS,
)

celery_app.autodiscover_tasks(['src.celery.tasks'])

celery_app.conf.beat_schedule = {
    'daily-reminders': {
        'task': 'src.celery.tasks.daily_reminders.send_daily_reminders',
        'schedule': crontab(minute=0, hour=9),
    },
}
