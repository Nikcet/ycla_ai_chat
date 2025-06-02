from uuid import uuid4
from shortuuid import uuid
from sqlmodel import create_engine, Session, select, delete
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    CorsOptions,
    SearchIndex,
    ScoringProfile,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    LexicalAnalyzerName,
)

from app import logger, settings
from app.models import Company, FileMetadata, AdminPrompt
from app.utils import create_batch, encode_document_key


engine = create_engine(settings.sqlite_url)


def get_search_client(index_name: str = settings.search_index):
   """
   Get a search client.

   Args:
       index_name (str): The name of the search index.

   Returns:
       SearchClient: The search client object.

   Raises:
       Exception: If the search client cannot be created.
   """
   client = SearchClient(
       endpoint=settings.search_endpoint,
       index_name=index_name,
       credential=AzureKeyCredential(settings.search_admin_key),
   )
   if client is None:
       raise Exception("Failed to create search client.")

   logger.info("Created search client.")
   return client


def get_async_search_client(index_name: str = settings.search_index):
   """
   Get an asynchronous search client.

   Args:
       index_name (str): The name of the search index.

   Returns:
       SearchClient: The asynchronous search client object.

   Raises:
       Exception: If the search client cannot be created.
   """
   client = SearchClient(
       endpoint=settings.search_endpoint,
       index_name=index_name,
       credential=AzureKeyCredential(settings.search_admin_key),
   )
   if client is None:
       raise Exception("Failed to create search client.")

   logger.info("Created search client.")
   return client


def create_search_client(company_id: int):
   """
   Create a search client.

   Args:
       company_id (int): The ID of the company.

   Returns:
       SearchClient: The search client object.

   Raises:
       Exception: If the search client cannot be created.
   """
   client = SearchIndexClient(
       endpoint=settings.search_endpoint,
       credential=AzureKeyCredential(settings.search_admin_key),
   )
   name = settings.search_index + "-ai-chat-" + str(company_id)
   fields = [
       SimpleField(name="id", type=SearchFieldDataType.String, key=True),
       SearchableField(
           name="company_id", type=SearchFieldDataType.String, filterable=True
       ),
       SearchableField(
           name="document_id", type=SearchFieldDataType.String, filterable=True
       ),
       SearchableField(
           name="content",
           type=SearchFieldDataType.String,
           filterable=True,
           analyzer_name=LexicalAnalyzerName.STANDARD_LUCENE,
       ),
       SearchableField(
           name="embeddings",
           type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
       ),
   ]
   cors_options = CorsOptions(allowed_origins=["*"], max_age_in_seconds=3600)
   scoring_profiles: list[ScoringProfile] = []
   index = SearchIndex(
       name=name,
       fields=fields,
       scoring_profiles=scoring_profiles,
       cors_options=cors_options,
   )
   result = client.create_index(index)
   if result is None:
       raise Exception("Failed to create search client.")

   logger.info("Created admin client.")
   return get_search_client(name)

def upload_documents(documents: list[str], company_id: str) -> dict[str, bool]:
    try:
        for file_path in documents:
            doc_id = uuid()
            batch = create_batch(
                company_id=company_id, file_path=file_path, document_id=doc_id
            )

            for doc in batch:
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


def delete_documents(company_id: str) -> dict[str, bool]:
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


def delete_document_by_id(document_id: str) -> dict[str, bool]:
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


def create_company(company_name: str, session: Session) -> Company | dict[str, bool]:
    try:
        company = Company(name=company_name, api_key=str(uuid4()))
        session.add(company)
        session.commit()
        return company
    except Exception as e:
        logger.error(f"Error while creating company '{company_name}': {e}")
        return {"created": False}


def save_admin_prompt(
    admin_prompt: AdminPrompt, company: Company, session: Session
) -> dict[str, bool]:
    old_prompt = session.exec(
        select(AdminPrompt).where(AdminPrompt.company_id == company.id)
    ).first()
    if old_prompt:
        session.delete(old_prompt)
        session.commit()

    new_prompt = AdminPrompt(prompt=admin_prompt.prompt, company_id=company.id)
    session.add(new_prompt)
    session.commit()


def get_admin_prompt(company: Company, session: Session) -> AdminPrompt:
    admin_prompt = ""

    prompt_record = session.exec(
        select(AdminPrompt).where(AdminPrompt.company_id == company.id)
    ).first()
    if prompt_record:
        admin_prompt = prompt_record.prompt

    return admin_prompt


# search_client = get_search_client()
search_client = get_async_search_client()
# admin_client = create_search_client()
