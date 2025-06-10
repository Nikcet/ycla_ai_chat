from pydantic import BaseModel, Field, HttpUrl
from typing import Any


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Ycla AI"])


class RegisterResponse(BaseModel):
    api_key: str
    message: str


class UploadRequest(BaseModel):
    documents: list[str] = Field(
        ...,
        examples=[["path/to/doc1.pdf", "doc2.docx"]],
        description="List of documents filenames to upload",
    )


class ChatRequest(BaseModel):
    question: str


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
    prompt: str


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


class UploadWithWebhookRequest(BaseModel):
    documents: list[str] = Field(
        ...,
        examples=[["path/to/doc1.pdf", "doc2.docx"]],
        description="List of document filenames to upload",
    )
    webhook_url: HttpUrl = Field(
        ...,
        examples=["https://client.example.com/webhook"],
        description="Valid HTTPS URL for result notification",
    )


class DeleteDocumentResponse(BaseModel):
    status: dict[str, bool]

    class Config:
        schema_extra = {"example": {"status": {"success": True}}}
