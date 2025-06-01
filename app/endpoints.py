from fastapi import APIRouter, Depends
from azure.search.documents.models import VectorizedQuery

from shortuuid import uuid
from sqlmodel import Session, delete
from openai.lib.azure import AzureOpenAI
from celery.result import AsyncResult


from app.schemas import (
    RegisterResponse,
    RegisterRequest,
    UploadRequest,
    ChatResponse,
    ChatRequest,
)
from app import logger
from app.models import Company, FileMetadata
from app.dependencies import (
    get_company_session,
    get_current_company,
    delete_documents,
    delete_document_by_id,
)
from app.database import search_client
from app.utils import get_embedding
from app.config import get_app_settings
from app.celery_worker import celery_tasks

from app.tasks import upload_documents_task

settings = get_app_settings()
router = APIRouter()

client = AzureOpenAI(
    api_key=settings.api_key,
    api_version=settings.api_version,
    azure_endpoint=settings.endpoint,
)


@router.post("/register", response_model=RegisterResponse)
async def register_company(
    req: RegisterRequest, session: Session = Depends(get_company_session)
):
    company = Company(name=req.name, id=uuid(req.name))
    session.add(company)
    session.commit()
    return RegisterResponse(api_key=company.api_key)


@router.post(
    "/documents/upload",
    dependencies=[Depends(get_current_company), Depends(get_company_session)],
)
async def upload(
    req: UploadRequest,
    company: Company = Depends(get_current_company),
):
    logger.info(f"Uploading documents for company {company.id}")
    task = upload_documents_task.delay(documents=req.documents, company_id=company.id)
    return {"task_id": task.task_id}

    # res = upload_documents(req.documents, company_id=company.id, session=session)

    # return {"status": res}


@router.post(
    "/documents/delete/all",
    dependencies=[Depends(get_current_company), Depends(get_company_session)],
)
async def delete_all_documents(
    company: Company = Depends(get_current_company),
):
    res = delete_documents(company_id=company.id)

    return {"status": res}


@router.post(
    "/documents/delete/{document_id}",
    dependencies=[Depends(get_current_company), Depends(get_company_session)],
)
async def delete_document(
    document_id: str,
    company: Company = Depends(get_current_company),
):
    res = delete_document_by_id(document_id=document_id)

    return {"status": res}


@router.get("/documents/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    task = AsyncResult(task_id, app=celery_tasks)
    logger.info(f"Task status is ready: {task.ready()}")
    return {"status": task.status, "result": task.result}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, company: Company = Depends(get_current_company)):
    q_emb = get_embedding(req.question)
    vectorized_query = VectorizedQuery(
        vector=q_emb,
        k_nearest_neighbors=3,
        fields="embedding",
    )
    results = search_client.search(
        search_text="*",
        vector_queries=[vectorized_query],
        filter=f"company_id eq '{company.id}'",
    )

    # TODO: Реализовать асинхронный поиск в БД

    context = "\n".join([doc["content"] for doc in results])
    messages = [
        {
            "role": "system",
            "content": "Используй только предоставленный контекст для ответа.",
        },
        {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}"},
    ]

    response = client.chat.completions.create(
        model=settings.model_name,
        messages=messages,
        stream=False,
    )
    return ChatResponse(answer=response.choices[0].message.content)
