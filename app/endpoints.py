import json
from pydantic import ValidationError, HttpUrl
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    File,
    UploadFile,
    Form,
    Path,
)
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
from app.models import Company
from app.utils import get_embedding, get_redis_history, set_redis_history
from app.celery_worker import celery_tasks
from app.tasks import upload_documents_task, delete_documents_task, delete_company_task
from app.clients import azure_client, deepseek_client, search_client, redis, engine
from app.schemas import (
    RegisterResponse,
    RegisterRequest,
    ChatRequest,
    TaskResponse,
    TaskStatusResponse,
    AdminPromptRequest,
    WebhookRequest,
    HealthResponse,
    DeleteDocumentResponse,
    DocumentListResponse,
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
                        "message": "Company 'Acme Inc' registered successfully",
                    }
                }
            },
        },
        status.HTTP_409_CONFLICT: {
            "description": "Company with this name already exists",
            "content": {
                "application/json": {
                    "example": {"detail": "Company 'Acme Inc' already exists"}
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during registration",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to register company: Database error"}
                }
            },
        },
    },
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_company(
    req: RegisterRequest, session: Session = Depends(get_company_session)
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
                detail=f"Company '{req.name}' already exists",
            )

        company = create_company(req.name, session)

        return RegisterResponse(
            api_key=company.api_key,
            message=f"Company '{req.name}' registered successfully",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Company registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register company: {str(e)}",
        )


@router.delete(
    "/company/delete",
    tags=["Company"],
    summary="Delete a company",
    response_description="Task ID for the deletion operation",
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Deletion task successfully queued",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "message": "Company deletion task started. Results will be sent to https://webhook.example.com",
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid webhook URL",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid webhook URL format"}
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Failed to queue deletion task",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to start deletion task: Broker connection error"
                    }
                }
            },
        },
    },
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_company(
    body: WebhookRequest,
    company: Company = Depends(get_current_company),
):
    """
    Initiate company deletion process as an asynchronous task.

    Process:
    1. Validate webhook URL format
    2. Queue deletion task in Celery
    3. Return task ID for tracking

    Important:
    - Actual deletion happens asynchronously
    - Results will be sent to the provided webhook URL
    - This action is irreversible

    Args:
        body (WebhookRequest):

            - webhook_url: URL to receive deletion result notification

    Returns:
        TaskResponse:

            - task_id: Celery task ID for tracking
            - message: Confirmation message with webhook URL
    """
    try:
        task = delete_company_task.delay(
            company_id=company.id, url=str(body.webhook_url)
        )

        return TaskResponse(
            task_id=task.id,
            message=f"Company deletion task started. Results will be sent to {body.webhook_url}",
            monitoring_url=f"/company/delete/status/{task.id}",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to start deletion task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start deletion task: {str(e)}",
        )


@router.post(
    "/documents/upload",
    tags=["Documents"],
    summary="Upload documents for a company",
    response_description="Task ID for the upload operation",
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Upload task successfully queued",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "message": "Document upload task started. Results will be sent to https://webhook.example.com",
                        "monitoring_url": "/documents/upload/status/550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Validation error, unsupported file type, or file too large",
            "content": {
                "application/json": {
                    "examples": {
                        "Invalid file type": {
                            "value": {"detail": "Unsupported file type: .xlsx"}
                        },
                        "File too large": {
                            "value": {"detail": "File 'report.pdf' exceeds 10 MB limit"}
                        },
                        "Invalid webhook URL": {
                            "value": {"detail": "Invalid webhook URL format"}
                        },
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during upload",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to start upload task: Broker connection error"
                    }
                }
            },
        },
    },
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload(
    webhook_url: HttpUrl = Form(...),
    files: list[UploadFile] = File(...),
    company: Company = Depends(get_current_company),
):
    """
    Initiate document upload process as an asynchronous task.

    Process:
    1. Validate uploaded files and webhook URL
    2. Read file content into memory
    3. Queue background task for document processing

    Important:
    - Actual upload happens asynchronously
    - Results will be sent to the provided webhook URL
    - **Only supports PDF and DOCX files**
    - Files must not exceed 100 MB
    - Azure AI Search upload is asynchronous, success response is immediate

    Args:

        webhook_url (HttpUrl): Valid HTTPS URL for result notification
        files (list[UploadFile]): List of files to upload. Must be PDF or DOCX format

    Returns:

        - task_id: Celery task ID for tracking
        - message: Confirmation with webhook URL
        - monitoring_url: URL to check task status
    """
    from pathlib import Path

    logger.info(
        f"Uploading documents for company: name - {company.name}, id - {company.id}"
    )

    file_data = []
    for file in files:
        if Path(file.filename).suffix.lower() not in settings.supported_extensions:
            logger.error(f"Unsupported file type: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type",
            )
        if file.size > settings.max_file_size:
            logger.error(f"File exceeds size limit: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds size limit",
            )
        try:
            file_data.append({"file": file.file.read(), "file_name": file.filename})
        except Exception as e:
            logger.error(f"Error reading file {file.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read file: {file.filename}",
            )

    logger.info(
        f"Received documents to upload: {len(file_data)}. Company: name - {company.name}, id - {company.id}"
    )
    try:
        task = upload_documents_task.delay(
            documents=file_data, company_id=company.id, url=str(webhook_url)
        )

        return TaskResponse(
            task_id=task.id,
            message=f"Document upload task started. Results will be sent to {webhook_url}",
            monitoring_url=f"/documents/upload/status/{task.id}",
        )
    except ValidationError as ve:
        logger.error(f"Validation error in request body: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request body"
        )
    except KeyError as ke:
        logger.error(f"Missing required field in request body: {ke}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {ke}",
        )

    except Exception as e:
        logger.error(f"Failed to start upload task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start upload task: {e}",
        )


@router.delete(
    "/documents/delete/all",
    tags=["Documents"],
    summary="Delete all documents for a company asynchronously",
    response_description="Task ID for the deletion operation",
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Deletion task successfully queued",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "message": "All documents deletion task started. Results will be sent to https://webhook.example.com",
                        "monitoring_url": "/documents/delete/status/550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid webhook URL format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid webhook URL format"}
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Failed to queue deletion task",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to start deletion task: Broker connection error"
                    }
                }
            },
        },
    },
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_all_documents(
    body: WebhookRequest,
    company: Company = Depends(get_current_company),
):
    """
    Initiate asynchronous deletion of all documents for the current company.

    Process:
    1. Validate webhook URL format
    2. Queue deletion task in Celery
    3. Return task ID for tracking

    Important:
    - Actual deletion happens asynchronously
    - Results will be sent to the provided webhook URL
    - This action is irreversible and affects all documents
    - **Azure AI Search deletion is asynchronous, so it can take some time to finish after success response.**

    Args:

        - webhook_url: URL to receive deletion result notification

    Returns:

        - task_id: Celery task ID for tracking
        - message: Confirmation message with webhook URL
        - monitoring_url: URL to check task status
    """
    try:
        logger.info(f"Initiating deletion of all documents for company {company.id}")

        task = delete_documents_task.delay(
            company_id=company.id, url=str(body.webhook_url)
        )

        return TaskResponse(
            task_id=task.id,
            message=f"All documents deletion task started. Results will be sent to {body.webhook_url}",
            monitoring_url=f"/documents/delete/status/{task.id}",
        )

    except ValidationError as ve:
        logger.error(f"Validation error in webhook URL: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook URL format"
        )

    except Exception as e:
        logger.error(f"Failed to start deletion task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start deletion task: {str(e)}",
        )


@router.delete(
    "/documents/delete/{document_id}",
    tags=["Documents"],
    summary="Delete a document by ID for a company",
    response_description="Result of the document deletion operation",
    responses={
        status.HTTP_200_OK: {
            "description": "Document successfully deleted",
            "content": {"application/json": {"example": {"status": {"success": True}}}},
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Document with ID '123' not found"}
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during deletion",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to delete document: Database error"}
                }
            },
        },
    },
    response_model=DeleteDocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_document(
    document_id: str = Path(..., description="The ID of the document to delete"),
    company: Company = Depends(get_current_company),
):
    """
    Delete a specific document for the current company.

    Process:
    1. Validate document existence
    2. Perform document deletion
    3. Return deletion result

    Important:
    - This operation is irreversible
    - Requires valid company authentication
    - **ID is stored in the database PostgreSQL in table "FileMetadata" with key "document_id".**

    Args:

        document_id (str):
            The unique identifier of the document to delete.


    Returns:

        DeleteDocumentResponse:
            - status: Dictionary with key "success" and boolean value
    """
    try:
        logger.info(f"Deleting document {document_id} for company {company.id}")

        result = delete_document_by_id(document_id=document_id)

        if not result or not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' not found",
            )

        logger.info(f"Document deleted successfully: {document_id}")

        return DeleteDocumentResponse(status=result)  # {"success": True}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        )


@router.get(
    "/documents",
    tags=["Documents"],
    summary="Get all documents for the current company",
    response_description="List of documents for the company",
    responses={
        status.HTTP_200_OK: {
            "description": "List of documents successfully retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "documents": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "file_name": "report.pdf",
                                "company_id": "company_001",
                                "document_id": "doc_123",
                            },
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "file_name": "presentation.pptx",
                                "company_id": "company_001",
                                "document_id": "doc_456",
                            },
                        ]
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error while fetching documents",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to fetch documents: Database error"}
                }
            },
        },
    },
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_documents_for_company(
    company: Company = Depends(get_current_company),
) -> DocumentListResponse:
    """
    Retrieve all documents for the current authenticated company.

    Process:
    1. Fetch documents from storage by company ID
    2. Return list of document metadata

    Important:
    - Returns empty list if no documents found
    - Requires valid company authentication
    - Each file contains metadata like ID, name, company association, and document ID for search

    Returns:

        - documents: List of file metadata objects (empty if none found)
    """
    try:
        logger.info(f"Fetching documents for company {company.id}")

        result = get_documents(company_id=company.id)

        if result is None:
            logger.info(f"No documents found for company {company.id}")
            return DocumentListResponse(documents=[])

        logger.info(f"Found {len(result)} documents for company {company.id}")
        return DocumentListResponse(documents=result)

    except Exception as e:
        logger.error(f"Failed to fetch documents for company {company.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch documents: {str(e)}",
        )


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


@router.post(
    "/chat",
    tags=["Chat"],
    summary="Handle a chat request using company-specific knowledge base",
    response_description="Answer to the question with updated JWT token",
    responses={
        status.HTTP_200_OK: {
            "description": "Successful response with answer",
            "content": {
                "application/json": {
                    "example": {
                        "answer": "The answer to your question is based on the provided context."
                    }
                }
            },
            "headers": {
                "x-jwt-token": {
                    "description": "Updated JWT token for subsequent requests",
                    "schema": {"type": "string"},
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "AI service unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve response from Azure OpenAI or Deepseek API. Try later."
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Unexpected error. Failed to retrieve response from AI API"
                    }
                }
            },
        },
    },
    status_code=status.HTTP_200_OK,
)
async def chat(
    req: ChatRequest,
    company: Company = Depends(get_current_company),
    session_data: tuple = Depends(get_session_from_jwt),
    session: Session = Depends(get_company_session),
    redis=Depends(get_redis_connection),
    search_client=Depends(get_search_client),
):
    """
    Process a chat request using company-specific knowledge base and conversation history.

    Process:
    1. Validate authentication and session
    2. Retrieve conversation history from Redis
    3. Search relevant documents using vector similarity
    4. Generate answer using AI model (Azure/OpenAI or fallback to Deepseek)
    5. Save conversation history
    6. Return answer with updated JWT token

    Important:
    - Uses Redis to maintain conversation state
    - Supports multiple AI backends with fallback mechanism
    - Requires valid company authentication
    - JWT token is automatically refreshed in headers

    Args:

        - question: User's query text

    Returns:
        - answer: Generated response to the question
        - x-jwt-token: Updated JWT token in headers for subsequent requests

    Raises:

        HTTPException:
            - 401: Invalid authentication credentials
            - 503: AI service unavailable
            - 500: Unexpected internal server error
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


@router.delete(
    "/chat/clear",
    tags=["Chat"],
    summary="Clear all chat history for the current company",
    response_description="Confirmation of deletion",
    responses={
        status.HTTP_200_OK: {
            "description": "History cleared successfully",
            "content": {
                "application/json": {"example": {"detail": "Chat history cleared"}}
            },
            "headers": {
                "x-jwt-token": {
                    "description": "Updated JWT token for subsequent requests",
                    "schema": {"type": "string"},
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during deletion",
        },
    },
    status_code=status.HTTP_200_OK,
)
async def clear_chat_history(
    company: Company = Depends(get_current_company),
    session_data: tuple = Depends(get_session_from_jwt),
    redis=Depends(get_redis_connection),
):
    """
    Delete all chat history for the current company.

    Process:
    1. Validate company authentication
    2. Find all Redis keys matching company history pattern
    3. Delete all found keys

    Important:
    - Affects all chat sessions within the company
    - Irreversible operation

    Returns:
    
        - detail: Operation result message
        - x-jwt-token: Updated JWT token in headers

    Raises:
    
        HTTPException:
            - 401: Invalid authentication
            - 500: Redis operation error
    """
    _, jwt_token = session_data  # Session ID not needed for this operation
    pattern = f"history:{company.id}:*"

    try:
        # Find all keys matching company pattern
        keys = []
        cursor = "0"
        while cursor != 0:
            cursor, partial_keys = await redis.scan(cursor, match=pattern, count=1000)
            keys.extend(partial_keys)

        # Delete keys if found
        if keys:
            await redis.delete(*keys)
            msg = f"Deleted {len(keys)} chat sessions"
        else:
            msg = "No chat history found"

        logger.info(f"{msg} for company {company.id}")
        return JSONResponse(content={"detail": msg}, headers={"x-jwt-token": jwt_token})

    except Exception as e:
        logger.error(f"Redis clearance error for company {company.id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during history clearance"
        )


@router.get(
    "/chat/sessions",
    tags=["Chat"],
    summary="Get count of active chat sessions for the company",
    response_description="Number of active sessions",
    responses={
        status.HTTP_200_OK: {
            "description": "Successful response with session count",
            "content": {
                "application/json": {
                    "example": {"count": 5}
                }
            },
            "headers": {
                "x-jwt-token": {
                    "description": "Updated JWT token for subsequent requests",
                    "schema": {"type": "string"},
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Redis operation error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve session count"}
                }
            },
        },
    },
)
async def get_active_sessions_count(
    company: Company = Depends(get_current_company),
    session_data: tuple = Depends(get_session_from_jwt),
    redis=Depends(get_redis_connection),
):
    """
    Get the count of active chat sessions for the current company.

    Process:
    1. Validate company authentication
    2. Scan Redis keys matching company session pattern
    3. Count matching keys

    Important:
    - Active session = any existing history key for the company
    - Uses efficient Redis SCAN instead of KEYS for large datasets

    Returns:
    
        - count: Number of active sessions
        - x-jwt-token: Updated JWT token in headers

    Raises:
    
        HTTPException:
            - 401: Invalid authentication
            - 500: Redis operation error
    """
    _, jwt_token = session_data
    pattern = f"history:{company.id}:*"
    session_count = 0

    try:
        cursor = '0'
        while cursor != 0:
            cursor, keys = await redis.scan(cursor, match=pattern, count=1000)
            session_count += len(keys)
        
        logger.info(f"Found {session_count} active sessions for company {company.id}")
        return JSONResponse(
            content={"count": session_count},
            headers={"x-jwt-token": jwt_token}
        )
            
    except Exception as e:
        logger.error(f"Redis count error for company {company.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve session count"
        )

@router.post(
    "/prompt",
    dependencies=[Depends(get_current_company), Depends(get_company_session)],
    tags=["Chat"],
    summary="Save or update the administrative prompt for a company",
    response_description="Result of the prompt saving operation",
    responses={
        status.HTTP_200_OK: {
            "description": "Prompt successfully saved",
            "content": {"application/json": {"example": {"saved": True}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid prompt format: Prompt must contain at least 5 characters"
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing API key",
            "content": {"application/json": {"example": {"detail": "Invalid API Key"}}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to save prompt: Database connection timeout"
                    }
                }
            },
        },
    },
    status_code=status.HTTP_200_OK,
)
async def save_prompt(
    req: AdminPromptRequest,
    company: Company = Depends(get_current_company),
    session: Session = Depends(get_company_session),
):
    """
    Save or update the administrative prompt for a company.

    Process:
    1. Validate incoming request data
    2. Save prompt to database
    3. Return operation result

    Important:
    - Requires valid company authentication
    - Overwrites existing prompt if one exists
    - Supports rich text formatting in prompt content

    Args:
        - prompt: New prompt text to save

    Returns:

        - saved: Boolean indicating success (True) or failure (False)

    Raises:

        HTTPException:
            - 400: Invalid request data
            - 401: Authentication failed
            - 500: Database operation error
    """
    try:
        logger.info(f"Saving admin prompt for company {company.id}")
        try:
            return {"saved": save_admin_prompt(req, company, session)}
        except ValidationError as ve:
            logger.error(f"Validation error in prompt request: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompt format: {ve}",
            )

        except Exception as e:
            logger.error(
                f"Critical error saving prompt for company {company.id}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save prompt: {str(e)}",
            )
    except Exception as e:
        logger.error(f"Error saving admin prompt: {e}")
        return {"saved": False}
