from fastapi import Header, HTTPException, Depends
from sqlmodel import Session, select, delete

from app import logger
from app.models import Company, FileMetadata
from app.config import get_app_settings
from app.database import engine, search_client
from app.utils import create_batch, encode_document_key
from shortuuid import uuid


app_settings = get_app_settings()


def get_company_session():
    with Session(engine) as session:
        yield session


def get_current_company(
    x_api_key: str = Header(...), session: Session = Depends(get_company_session)
) -> Company:
    company = session.exec(select(Company).where(Company.api_key == x_api_key)).first()
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return company


def upload_documents(documents: list[str], company_id: str) -> dict:
    try:
        for file_path in documents:
            doc_id = uuid()
            batch = create_batch(
                company_id=company_id, file_path=file_path, document_id=doc_id
            )

            for doc in batch:
                logger.info(f"Processing document: {doc}")
                doc["document_id"] = doc_id
                doc["id"] = encode_document_key(doc["id"])

            results = search_client.upload_documents(documents=batch)

            if results and results[0] and results[0].succeeded:
                with Session(engine) as session:
                    session.add(
                        FileMetadata(
                            file_name=file_path,
                            company_id=company_id,
                            document_id=doc_id,
                        )
                    )
                    session.commit()
            else:
                raise

        return {"indexed": True}
    except Exception as e:
        logger.error(f"Error while work with file '{file_path}': {e}")
        return {"indexed": False}


def delete_documents(company_id: str) -> dict:
    try:
        filter_query = f"company_id eq '{company_id}'"
        chunks = search_client.search(filter=filter_query, search_text="*")
        docs = [{"id": chunk["id"]} for chunk in chunks]
        results = search_client.delete_documents(documents=docs)

        with Session(engine) as session:
            if results and results[0] and results[0].succeeded:
                session.exec(
                    delete(FileMetadata).where(FileMetadata.company_id == company_id)
                )
                session.commit()

        return {"deleted": True}
    except Exception as e:
        logger.error(f"Error while deleting files: {e}")
        return {"deleted": False}


def delete_document_by_id(document_id: str) -> dict:
    try:
        filter_query = f"document_id eq '{document_id}'"
        chunks = search_client.search(filter=filter_query, search_text="*")
        docs = [{"id": chunk["id"]} for chunk in chunks]

        if not docs:
            return {"deleted": False, "error": "No document found"}

        results = search_client.delete_documents(documents=docs)

        with Session(engine) as session:
            if results and results[0] and results[0].succeeded:
                session.exec(
                    delete(FileMetadata).where(FileMetadata.document_id == document_id)
                )
                session.commit()
            else:
                raise
            
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Error while deleting file '{document_id}': {e}")
        return {"deleted": False}
