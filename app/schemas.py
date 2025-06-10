from pydantic import BaseModel, Field
from typing import Any


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Ycla AI"])


class RegisterResponse(BaseModel):
    api_key: str
    message: str


class UploadRequest(BaseModel):
    documents: list[str]


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class TaskResponse(BaseModel):
    task_id: str


class UploadResponse(BaseModel):
    status: dict[str, bool]


class TaskStatusResponse(BaseModel):
    status: str
    result: Any


class AdminPromptRequest(BaseModel):
    prompt: str


class WebhookRequest(BaseModel):
    webhook_url: str


class HealthResponse(BaseModel):
    status: bool
    message: str
    services: dict
