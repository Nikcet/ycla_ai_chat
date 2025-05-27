# from celery import shared_task
from app.utils import create_batch
from app.database import search_client
from app.celery_worker import celery_tasks
from app import logger


@celery_tasks.task
def upload_documents_task(documents: list[str], company_id: int) -> dict[str, bool]:
    try:
        for file_path in documents:
            batch = create_batch(company_id=company_id, file_path=file_path)
            search_client.upload_documents(documents=batch)
        return {"indexed": True}
    except Exception as e:
        logger.error(f"Ошибка при обработке файла '{file_path}': {e}")
        return {"indexed": False}
