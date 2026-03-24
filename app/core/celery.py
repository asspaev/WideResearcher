from celery import Celery

from app.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "wideresearcher",
    broker=f"redis://:{_settings.redis.password}@{_settings.redis.host}:{_settings.redis.port}/1",
    backend=f"redis://:{_settings.redis.password}@{_settings.redis.host}:{_settings.redis.port}/2",
    include=["app.tasks.research"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
