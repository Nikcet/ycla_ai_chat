from sqlmodel import Session, delete
from sqlalchemy.exc import SQLAlchemyError

from app import logger
from app.database import upload_documents, delete_documents
from app.celery_worker import celery_tasks
from app.models import Company, AdminPrompt
from app.clients import engine
from app.utils import send_webhook


@celery_tasks.task
def upload_documents_task(
    documents: list[dict], company_id: int, url: str
) -> dict[str, bool]:
    result = {
        "success": False,
        "company_id": company_id,
        "errors": [],
        "details": {
            "documents_uploaded": False,
        },
    }
    try:
        logger.info(f"Uploading documents to company_id: {company_id}")

        upload_documents(documents, company_id)

        result["details"]["documents_uploaded"] = True
        result["success"] = True
    except SQLAlchemyError as e:
        logger.error(f"Database error during upload for company {company_id}: {str(e)}")
        result["errors"].append(f"Database operation: {e}")
    except Exception as e:
        logger.error(f"Critical error during upload for company {company_id}: {str(e)}")
        result["errors"].append(f"Critical: {e}")
    finally:
        try:
            if url:
                response = send_webhook(url=url, payload=result)
                logger.info(
                    f"Webhook sent for company {company_id}, {response.status_code}"
                )
        except Exception as e:
            logger.error(f"Webhook failed for company {company_id}: {str(e)}")
            result["errors"].append(f"Webhook: {str(e)}")



@celery_tasks.task
def delete_documents_task(company_id: int, url: str) -> dict[str, bool]:
    result = {
        "success": False,
        "company_id": company_id,
        "errors": [],
        "details": {
            "documents_deleted": False,
        },
    }

    try:
        logger.info(f"Deleting documents to company_id: {company_id}")
        delete_documents(company_id)

        result["details"]["documents_deleted"] = True
        result["success"] = True
    except SQLAlchemyError as e:
        logger.error(
            f"Critical error during deletion for company {company_id}: {str(e)}"
        )
        result["errors"].append(f"Critical: {str(e)}")

    finally:
        try:
            if url:
                response = send_webhook(url=url, payload=result)
                logger.info(
                    f"Webhook sent for company {company_id}, {response.status_code}"
                )
        except Exception as e:
            logger.error(f"Webhook failed for company {company_id}: {str(e)}")
            result["errors"].append(f"Webhook: {str(e)}")



@celery_tasks.task(max_retries=3, default_retry_delay=60)
def delete_company_task(company_id: str, url: str | None = None):
    result = {
        "success": False,
        "company_id": company_id,
        "errors": [],
        "details": {
            "documents_deleted": False,
            "prompts_deleted": False,
            "company_deleted": False,
        },
    }

    try:
        try:
            delete_documents(company_id)
            result["details"]["documents_deleted"] = True
        except Exception as e:
            logger.error(f"Error deleting documents for company {company_id}: {str(e)}")
            result["errors"].append(f"Documents deletion: {str(e)}")

        try:
            with Session(engine) as session:
                deleted_prompts = session.exec(
                    delete(AdminPrompt).where(AdminPrompt.company_id == company_id)
                )
                result["details"]["prompts_deleted"] = deleted_prompts.rowcount > 0

                company = session.get(Company, company_id)
                if company:
                    session.delete(company)
                    session.commit()
                    result["details"]["company_deleted"] = True
                    result["success"] = True
                else:
                    result["errors"].append("Company not found")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error for company {company_id}: {str(e)}")
            result["errors"].append(f"Database operation: {str(e)}")
            raise

    except Exception as e:
        logger.exception(f"Critical error during deletion for company {company_id}")
        result["errors"].append(f"Critical: {str(e)}")

    finally:
        if url:
            try:
                send_webhook(url=url, payload=result)
            except Exception as e:
                logger.error(f"Webhook failed for company {company_id}: {str(e)}")
                result["errors"].append(f"Webhook: {str(e)}")

