from sqlmodel import Session, delete

from app import logger
from app.database import upload_documents, delete_documents
from app.celery_worker import celery_tasks
from app.models import Company, AdminPrompt
from app.clients import engine


@celery_tasks.task
def upload_documents_task(documents: list[str], company_id: int) -> dict[str, bool]:
    logger.info(f"Uploading documents to company_id: {company_id}")
    return upload_documents(documents, company_id)

@celery_tasks.task
def delete_documents_task(company_id: int) -> dict[str, bool]:
    logger.info(f"Deleting documents to company_id: {company_id}")
    return delete_documents(company_id)

@celery_tasks.task
def delete_company_task(company_id: str):
    try:
        delete_result = delete_documents(company_id)
        if not delete_result.get("deleted"):
            raise Exception(f"Failed to delete documents for company {company_id}")
        
        with Session(engine) as session:
            session.exec(delete(AdminPrompt).where(AdminPrompt.company_id == company_id))
            session.commit()
        
        with Session(engine) as session:
            company = session.get(Company, company_id)
            if company:
                session.delete(company)
                session.commit()
        
        return {"deleted": True, "company_id": company_id}
    
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {e}")
        return {"deleted": False, "error": str(e)}