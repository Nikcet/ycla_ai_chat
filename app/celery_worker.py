from celery import Celery
from app.config import get_app_settings

settings = get_app_settings()

celery_tasks = Celery(
    "tasks",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}",
    include=["app.tasks"],
)

celery_tasks.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
