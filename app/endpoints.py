import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from azure.search.documents.models import VectorizedQuery
from sqlmodel import Session
from celery.result import AsyncResult
from openai import (
    APIError,
    RateLimitError,
    InternalServerError,
    LengthFinishReasonError,
    ContentFilterFinishReasonError,
)

from app import logger, settings
from app.models import Company, FileMetadata
from app.utils import get_embedding, get_redis_history, set_redis_history
from app.celery_worker import celery_tasks
from app.tasks import upload_documents_task, delete_documents_task, delete_company_task
from app.clients import azure_client, deepseek_client
from app.schemas import (
    RegisterResponse,
    RegisterRequest,
    UploadRequest,
    ChatRequest,
    TaskResponse,
    UploadResponse,
    TaskStatusResponse,
    AdminPromptRequest,
    WebhookRequest,
)
from app.database import (
    delete_document_by_id,
    create_company,
    save_admin_prompt,
    get_admin_prompt,
    get_documents,
)
from app.dependencies import (
    get_company_session,
    get_current_company,
    get_session_from_jwt,
    get_redis_connection,
    get_search_client,
)


router = APIRouter()


@router.get("/")
async def root():
    return {"status": True}


@router.post("/company/register", response_model=RegisterResponse)
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


@router.delete("/company/delete", response_model=TaskResponse)
async def delete_company(
    body: WebhookRequest,
    company: Company = Depends(get_current_company),
):
    """
    Delete a company.

    Args:
        x-apy-key (Header): Company API key from header.
        webhook_url (str): Webhook URL to send task result.

    Returns:
        TaskResponse: The response object containing the task ID.
    """
    task = delete_company_task.delay(company_id=company.id, url=body.webhook_url)
    return TaskResponse(task_id=task.id)


@router.post(
    "/documents/upload",
    dependencies=[Depends(get_current_company)],
)
async def upload(
    body: dict,
    company: Company = Depends(get_current_company),
):
    """
    Upload documents for a company.

    Args:
        req (UploadRequest): The request object containing the documents to upload.
        x-apy-key (Header): Company API key from header.
        webhook_url (str): Webhook URL to send task result.

    Returns:
        TaskResponse: The response object containing the task ID.
    """
    try:
        req = UploadRequest(**body)
        webhook = WebhookRequest(**body)
    except Exception as e:
        logger.error(f"Error while parsing request body: {e}")
        return UploadResponse(status="failed", message="Invalid request body")
        
    task = upload_documents_task.delay(documents=req.documents, company_id=company.id, url=webhook.webhook_url)
    return TaskResponse(task_id=task.task_id)


@router.delete(
    "/documents/delete/all",
    dependencies=[Depends(get_current_company)],
)
async def delete_all_documents(
    body: WebhookRequest,
    company: Company = Depends(get_current_company),
):
    """
    Delete all documents for a company.

    Args:
        x-apy-key (Header): Company API key from header.
        webhook_url (str): Webhook URL to send task result.

    Returns:
        TaskResponse: The response object containing the task ID.
    """
    task = delete_documents_task.delay(company_id=company.id, url=body.webhook_url)
    return TaskResponse(task_id=task.task_id)


@router.delete(
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
        x-apy-key (Header): Company API key from header.

    Returns:
        UploadResponse: The response object containing the result of the deletion.
    """
    logger.info(f"Deleting document {document_id} for company {company.id}")
    res = delete_document_by_id(document_id=document_id)
    logger.info(f"Document deleted successfully: {res}")
    return UploadResponse(status=res)


@router.get("/documents")
async def get_documents_for_company(
    company: Company = Depends(get_current_company),
) -> dict[str, list[FileMetadata]]:
    """
    Get all documents for the current company by ID.
    
    Args:
        **company_id (str)**: The ID of the company.

    Returns:
        list[FileMetadata]: A list of metafiles.
    """
    logger.info(f"Trying to get all documents for company {company.id}")
    result = get_documents(company_id=company.id)
    return {"documents": result}


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


@router.get("/company/delete/status/{task_id}")
async def get_company_deleting_status(task_id: str):
    """
    Get the status of a company deleting task.

    Args:
        task_id (str): The ID of the task to check.

    Returns:
        TaskStatusResponse: The response object containing the status and result of the task.
    """
    task = AsyncResult(task_id, app=celery_tasks)
    logger.info(f"Task status is ready: {task.ready()}")
    return TaskStatusResponse(status=task.status, result=task.result)


@router.post("/chat")
async def chat(
    req: ChatRequest,
    company: Company = Depends(get_current_company),
    session_data: tuple = Depends(get_session_from_jwt),
    session: Session = Depends(get_company_session),
    redis=Depends(get_redis_connection),
    search_client=Depends(get_search_client),
):
    """
    Handle a chat request and return a response.

    Args:
        req (ChatRequest): The request object containing the question.
        x-apy-key (Header): Company API key from header.
        x-jwt-token (Header): JWT token from header "Authorization". If is not, it will be created. Starts with "Bearer ".

    Returns:
        JSONResponse: The response object containing the answer and jwt in header.

    Raises:
        HTTPException: If there is an error while handling the chat request.
    """

    session_id, jwt_token = session_data

    try:
        messages = await get_redis_history(redis, f"history:{company.id}:{session_id}")
    except Exception as e:
        logger.error(f"Error getting redis history: {e}")
        messages = []
    try:
        q_emb = get_embedding(req.question)

        vectorized_query = VectorizedQuery(
            vector=q_emb,
            k_nearest_neighbors=settings.nearest_neighbors,
            fields="embedding",
        )

        logger.info(f"Searching for documents for company {company.id}")
        results = search_client.search(
            search_text="*",
            vector_queries=[vectorized_query],
            filter=f"company_id eq '{company.id}'",
        )
        logger.info(f"Found documents for company {company.id}")
        context = "\n".join([doc["content"] for doc in results])
    except Exception as e:
        logger.error(f"Error searching for documents: {e}")
        context = ""

    logger.info("Context is completed.")

    admin_prompt = get_admin_prompt(company, session)
    logger.info(f"Admin prompt: {admin_prompt}")

    system_prompt = [
        {
            "role": "system",
            "content": f"Используй только предоставленный контекст для ответа. {admin_prompt}",
        }
    ]
    messages.append(
        {
            "role": "user",
            "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}",
        }
    )
    try:
        final_messages = system_prompt + messages
    except TypeError as e:
        logger.error(f"Error appending messages: {e}: {messages}")
        final_messages = system_prompt + [
            {
                "role": "user",
                "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}",
            }
        ]
    except Exception as e:
        logger.error(f"Unexpected error appending messages: {e}")
        final_messages = system_prompt + [
            {
                "role": "user",
                "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}",
            }
        ]

    logger.info("Final messages is completed.")

    try:
        client = azure_client

        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=final_messages,
            stream=False,
        )
    except (
        APIError,
        RateLimitError,
        InternalServerError,
        LengthFinishReasonError,
        ContentFilterFinishReasonError,
    ) as e:
        logger.warning(
            f"Azure OpenAI is not available. Trying to use Deepseek API. {e}"
        )
        client = deepseek_client
        try:
            response = await client.chat.completions.create(
                model=settings.model_name,
                messages=final_messages,
            )
        except Exception as e:
            logger.error(f"Error using Deepseek API: {e}")
            raise HTTPException(
                status_code=503,
                detail="Failed to retrieve response from Azure OpenAI or Deepseek API. Try later.",
            )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unexpected error. Failed to retrieve response from Azure OpenAI or Deepseek API",
        )

    answer = response.choices[0].message.content
    logger.info(f"Answer is ready for company {company.id}")

    try:
        await set_redis_history(
            redis,
            f"history:{company.id}:{session_id}",
            json.dumps({"role": "user", "content": req.question}),
            json.dumps({"role": "assistant", "content": answer}),
        )
        logger.info(f"Chat history is saved successfully for company {company.id}")
    except Exception as e:
        logger.error(f"Error saving chat history: {e} for company {company.id}")

    return JSONResponse(content={"answer": answer}, headers={"x-jwt-token": jwt_token})


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

    Returns:
        dict: A dictionary with a success status.

    Raises:
        HTTPException: If there is an error while saving the admin prompt.
    """
    try:
        logger.info(f"Saving admin prompt for company {company.id}")
        try:
            save_admin_prompt(req, company, session)
            return {"saved": True}
        except Exception as e:
            logger.error(f"Error saving admin prompt: {e}")
            raise HTTPException(status_code=500, detail="Failed to save admin prompt")
    except Exception as e:
        logger.error(f"Error saving admin prompt: {e}")
        return {"saved": False}
