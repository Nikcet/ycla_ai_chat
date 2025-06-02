from app.database import upload_documents, delete_documents
from app.celery_worker import celery_tasks
from app import logger


@celery_tasks.task
def upload_documents_task(documents: list[str], company_id: int) -> dict[str, bool]:
    logger.info(f"Uploading documents to company_id: {company_id}")
    return upload_documents(documents, company_id)

@celery_tasks.task
def delete_documents_task(company_id: int) -> dict[str, bool]:
    logger.info(f"Deleting documents to company_id: {company_id}")
    return delete_documents(company_id)