from fastapi import APIRouter, Depends, HTTPException, Header
from azure.search.documents.models import VectorizedQuery
from redis import asyncio as aioredis
import json
from uuid import uuid4

from sqlmodel import Session
from openai.lib.azure import AzureOpenAI
from celery.result import AsyncResult

from app.schemas import (
    RegisterResponse,
    RegisterRequest,
    UploadRequest,
    ChatResponse,
    ChatRequest,
    TaskResponse,
    UploadResponse,
    TaskStatusResponse,
    AdminPromptRequest,
)
from app import logger
from app.models import Company
from app.dependencies import (
    get_company_session,
    get_current_company,
    delete_document_by_id,
    create_company,
    save_admin_prompt,
    get_admin_prompt,
    get_redis_connection,
)
from app.database import search_client
from app.utils import get_embedding
from app.config import get_app_settings
from app.celery_worker import celery_tasks

from app.tasks import upload_documents_task, delete_documents_task

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
    """
    Register a new company and return a response with an API key.

    Args:
        req (RegisterRequest): The request object containing the company name.

    Returns:
        RegisterResponse: The response object containing the API key.
    """
    company = create_company(req.name, session)
    return RegisterResponse(api_key=company.api_key)


@router.post(
    "/documents/upload",
    dependencies=[Depends(get_current_company)],
)
async def upload(
    req: UploadRequest,
    company: Company = Depends(get_current_company),
):
    """
    Upload documents for a company.

    Args:
        req (UploadRequest): The request object containing the documents to upload.
        company (Company): The company object for which the documents are being uploaded.

    Returns:
        TaskResponse: The response object containing the task ID.
    """
    task = upload_documents_task.delay(documents=req.documents, company_id=company.id)
    return TaskResponse(task_id=task.task_id)


@router.post(
    "/documents/delete/all",
    dependencies=[Depends(get_current_company)],
)
async def delete_all_documents(
    company: Company = Depends(get_current_company),
):
    """
    Delete all documents for a company.

    Args:
        company (Company): The company object for which the documents are being deleted.

    Returns:
        TaskResponse: The response object containing the task ID.
    """
    task = delete_documents_task.delay(company_id=company.id)
    return TaskResponse(task_id=task.task_id)


@router.post(
    "/documents/delete/{document_id}",
    dependencies=[Depends(get_current_company)],
)
async def delete_document(
    document_id: str,
    company: Company = Depends(get_current_company),
):
    """
    Delete a document by ID for a company.

    Args:
        document_id (str): The ID of the document to delete.
        company (Company): The company object for which the document is being deleted.

    Returns:
        UploadResponse: The response object containing the result of the deletion.
    """
    logger.info(f"Deleting document {document_id} for company {company.id}")
    res = delete_document_by_id(document_id=document_id)
    logger.info(f"Document deleted successfully: {res}")
    return UploadResponse(status=res)


@router.get("/documents/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    """
    Get the status of an upload task.

    Args:
        task_id (str): The ID of the task to check.

    Returns:
        TaskStatusResponse: The response object containing the status and result of the task.
    """
    task = AsyncResult(task_id, app=celery_tasks)
    logger.info(f"Task status is ready: {task.ready()}")
    return TaskStatusResponse(status=task.status, result=task.result)


@router.get("/documents/delete/status/{task_id}")
async def get_deleting_status(task_id: str):
    """
    Get the status of a deleting task.

    Args:
        task_id (str): The ID of the task to check.

    Returns:
        TaskStatusResponse: The response object containing the status and result of the task.
    """
    task = AsyncResult(task_id, app=celery_tasks)
    logger.info(f"Task status is ready: {task.ready()}")
    return TaskStatusResponse(status=task.status, result=task.result)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    company: Company = Depends(get_current_company),
    session: Session = Depends(get_company_session),
    session_id: str = Header(default=str(uuid4())),
    redis: aioredis.Redis = Depends(get_redis_connection),
):
    """
    Handle a chat request and return a response.

    Args:
        req (ChatRequest): The request object containing the question.
        company (Company): The company object for which the chat is being handled.
        session (Session): The database session.
        session_id (str): The ID of the chat session.
        redis (aioredis.Redis): The Redis connection.

    Returns:
        ChatResponse: The response object containing the answer.
    """

    history = await redis.lrange(f"history:{company.id}:{session_id}", 0, -1)
    messages = [json.loads(msg) for msg in history] if history else []

    q_emb = get_embedding(req.question)
    vectorized_query = VectorizedQuery(
        vector=q_emb,
        k_nearest_neighbors=settings.nearest_neighbors,
        fields="embedding",
    )
    # TODO: Реализовать асинхронный поиск в БД
    results = search_client.search(
        search_text="*",
        vector_queries=[vectorized_query],
        filter=f"company_id eq '{company.id}'",
    )

    context = "\n".join([doc["content"] for doc in results])

    admin_prompt = get_admin_prompt(company, session)

    system_prompt = [
        {
            "role": "system",
            "content": f"Используй только предоставленный контекст для ответа. {admin_prompt}",
        }
    ]

    final_messages = system_prompt + messages.append(
        {
            "role": "user",
            "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}",
        }
    )

    response = client.chat.completions.create(
        model=settings.model_name,
        messages=final_messages,
        stream=False,
    )

    answer = response.choices[0].message.content

    await redis.rpush(
        f"history:{company.id}:{session_id}",
        json.dumps({"role": "user", "content": req.question}),
        json.dumps({"role": "assistant", "content": answer}),
    )

    await redis.ltrim(f"history:{company.id}:{session_id}", -10, -1)

    return ChatResponse(answer=answer)


@router.post(
    "/prompt", dependencies=[Depends(get_current_company), Depends(get_company_session)]
)
async def save_prompt(
    req: AdminPromptRequest,
    company: Company = Depends(get_current_company),
    session: Session = Depends(get_company_session),
):
    """
    Save an admin prompt for a company.

    Args:
        req (AdminPromptRequest): The request object containing the prompt data.
        company (Company): The company object for which the prompt is being saved.
        session (Session): The database session.

    Returns:
        dict: A dictionary with a success status.

    Raises:
        HTTPException: If there is an error while saving the admin prompt.
    """
    try:
        logger.info(f"Saving admin prompt for company {company.id}")
        save_admin_prompt(req, company, session)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving admin prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to save admin prompt")
