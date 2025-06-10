import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from azure.search.documents.models import VectorizedQuery
from azure.core.exceptions import ServiceRequestError
from sqlmodel import Session, text, select, func
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
from app.clients import azure_client, deepseek_client, search_client, redis, engine
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
    HealthResponse,
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


@router.get(
    "/",
    tags=["Root"],
    summary="System Health Check",
    response_description="Critical service status report",
    responses={
        status.HTTP_200_OK: {
            "description": "All critical services are operational",
            "content": {
                "application/json": {
                    "example": {
                        "status": True,
                        "message": "All systems operational",
                        "services": {
                            "postgres": "OK",
                            "redis": "OK",
                            "azure_search": {
                                "status": "OK",
                                "documents_count": 1500,
                            },
                        },
                    }
                }
            },
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Critical service unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Service degradation detected",
                        "services": {
                            "postgres": "OK",
                            "redis": "FAILED: Connection timeout",
                            "azure_search": {
                                "status": "OK",
                                "documents_count": 1500,
                            },
                        },
                    }
                }
            },
        },
    },
    response_model=HealthResponse,
)
async def root():
    """
    Comprehensive health check of critical system dependencies.

    Verifies connectivity and basic functionality of:
    - PostgreSQL database
    - Redis cache and Celery-broker
    - Azure AI Search service

    For Azure AI Search, checks index statistics including:
    - Documents count
    """
    health_status = {
        "status": True,
        "message": "All systems operational",
        "services": {},
    }
    errors = []

    try:
        with Session(engine) as session:
            result = session.exec(text("SELECT 1")).one()
            if result[0] != 1:
                raise ConnectionError("PostgreSQL test query failed")
            health_status["services"]["postgres"] = "OK"
    except Exception as e:
        error_msg = f"PostgreSQL: {str(e)}"
        health_status["services"]["postgres"] = error_msg
        errors.append(error_msg)
        logger.error(error_msg)

    try:
        if await redis.ping():
            health_status["services"]["redis"] = "OK"
        else:
            raise ConnectionError("Redis ping failed")
    except Exception as e:
        error_msg = f"Redis: {str(e)}"
        health_status["services"]["redis"] = error_msg
        errors.append(error_msg)
        logger.error(error_msg)

    try:
        document_count = search_client.get_document_count()

        health_status["services"]["azure_search"] = {
            "status": "OK",
            "documents_count": document_count,
        }
    except ServiceRequestError as e:
        error_msg = f"Azure Search: {str(e)}"
        health_status["services"]["azure_search"] = {"status": error_msg}
        errors.append(error_msg)
        logger.error(error_msg)
    except Exception as e:
        error_msg = f"Azure Search: {str(e)}"
        health_status["services"]["azure_search"] = {"status": error_msg}
        errors.append(error_msg)
        logger.error(error_msg)

    if errors:
        health_status["status"] = False
        health_status["message"] = f"Service degradation: {len(errors)} critical issues"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_status
        )

    return HealthResponse(**health_status)


@router.post(
    "/company/register",
    tags=["Company"],
    summary="Register a new company",
    response_description="API key for the newly registered company",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Company successfully registered",
            "content": {
                "application/json": {
                    "example": {
                        "api_key": "sk-1234567890abcdef1234567890abcdef",
                        "message": "Company 'Acme Inc' registered successfully"
                    }
                }
            }
        },
        status.HTTP_409_CONFLICT: {
            "description": "Company with this name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Company 'Acme Inc' already exists"
                    }
                }
            }
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during registration",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to register company: Database error"
                    }
                }
            }
        }
    },
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED
)
async def register_company(
    req: RegisterRequest, 
    session: Session = Depends(get_company_session)
):
    """
    Register a new company and generate a unique API key.
    
    Process:
    1. Validate company name
    2. Check for existing company with same name
    3. Generate unique API key
    4. Persist company record in database
    
    Args:
        req (RegisterRequest): 
        
            - name: Legal name of the company
    
    Returns:
        RegisterResponse: 
        
            - api_key: Generated API key for the company
            - message: Success confirmation message
    """
    try:
        existing_company = session.exec(
            select(Company).where(func.lower(Company.name) == func.lower(req.name))
        ).first()
        
        if existing_company:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company '{req.name}' already exists"
            )
        
        company = create_company(req.name, session)
        
        return RegisterResponse(
            api_key=company.api_key,
            message=f"Company '{req.name}' registered successfully"
        )
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Company registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register company: {str(e)}"
        )

@router.delete("/company/delete", response_model=TaskResponse, tags=["Company"])
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
    "/documents/upload", dependencies=[Depends(get_current_company)], tags=["Documents"]
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

    task = upload_documents_task.delay(
        documents=req.documents, company_id=company.id, url=webhook.webhook_url
    )
    return TaskResponse(task_id=task.task_id)


@router.delete(
    "/documents/delete/all",
    dependencies=[Depends(get_current_company)],
    response_model=TaskResponse,
    tags=["Documents"],
)
async def delete_all_documents(
    body: WebhookRequest,
    company: Company = Depends(get_current_company),
):
    """
    Delete all documents for a company.

    Args:
        **x-apy-key (Header)**: Company API key from header.
        **webhook_url (str)**: Webhook URL to send task result.

    Returns:
        TaskResponse: The response object containing the task ID.
    """
    task = delete_documents_task.delay(company_id=company.id, url=body.webhook_url)
    return TaskResponse(task_id=task.task_id)


@router.delete(
    "/documents/delete/{document_id}",
    dependencies=[Depends(get_current_company)],
    tags=["Documents"],
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


@router.get("/documents", tags=["documents"])
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


@router.get("/documents/upload/status/{task_id}", tags=["Tasks status"])
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


@router.get("/documents/delete/status/{task_id}", tags=["Tasks status"])
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


@router.get("/company/delete/status/{task_id}", tags=["Tasks status"])
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


@router.post("/chat", tags=["Chat"])
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
    "/prompt",
    dependencies=[Depends(get_current_company), Depends(get_company_session)],
    tags=["Chat"],
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
