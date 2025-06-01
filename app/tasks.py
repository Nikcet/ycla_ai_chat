from sqlmodel import Session
# from celery import shared_task
# from app.utils import create_batch
# from app.database import search_client
from app.dependencies import upload_documents, delete_documents
from app.celery_worker import celery_tasks
# from app import logger


@celery_tasks.task
def upload_documents_task(documents: list[str], company_id: int) -> dict[str, bool]:
    return upload_documents(documents, company_id)

@celery_tasks.task
def delete_documents_task(company_id: int) -> dict[str, bool]:
    return delete_documents(company_id)