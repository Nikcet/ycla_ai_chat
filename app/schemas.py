from pydantic import BaseModel, Field, HttpUrl
from typing import Any
from app.models import FileMetadata


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Ycla AI"])


class RegisterResponse(BaseModel):
    api_key: str
    message: str


# class UploadRequest(BaseModel):
#     documents: list[str] = Field(
#         ...,
#         examples=[["path/to/doc1.pdf", "doc2.docx"]],
#         description="List of documents filenames to upload",
#     )


class ChatRequest(BaseModel):
    question: str = Field(..., examples=["Расскажите кратко о вашей компании"])


class ChatResponse(BaseModel):
    answer: str


class TaskResponse(BaseModel):
    task_id: str
    message: str
    monitoring_url: str


class UploadResponse(BaseModel):
    status: dict[str, bool]


class TaskStatusResponse(BaseModel):
    status: str
    result: Any


class AdminPromptRequest(BaseModel):
    prompt: str = Field(..., examples=["Ты - представитель компании ... "])


class WebhookRequest(BaseModel):
    webhook_url: HttpUrl = Field(
        ...,
        examples=["https://client.example.com/webhook"],
        description="Valid HTTPS URL",
    )


class HealthResponse(BaseModel):
    status: bool
    message: str
    services: dict


class UploadFileRequest(BaseModel):
    file: bytes = Field(..., description="Binary content of the uploaded file")
    file_name: str = Field(..., description="Name of the uploaded file")

    class Config:
        schema_extra = {"example": {"file": "binary_data", "file_name": "example.pdf"}}


class UploadRequest(BaseModel):
    files: list[UploadFileRequest] = Field(
        ...,
        description="List of uploaded files",
        examples=[["binary_file", "binary_file"]],
    )


class DeleteDocumentRequest(BaseModel):
    document_id: str


class UploadWithWebhookRequest(BaseModel):
    # files: list[UploadFileRequest] = Field(..., description="List of uploaded files")
    webhook_url: HttpUrl = Field(
        ...,
        examples=["https://client.example.com/webhook"],
        description="Valid HTTPS URL for result notification",
    )


class DeleteDocumentResponse(BaseModel):
    status: dict[str, bool]

    class Config:
        schema_extra = {"example": {"status": {"success": True}}}


class DocumentListResponse(BaseModel):
    documents: list[FileMetadata] = []

    class Config:
        schema_extra = {
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
