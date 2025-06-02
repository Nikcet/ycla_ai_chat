from pydantic import BaseModel
from typing import Any


class RegisterRequest(BaseModel):
    name: str


class RegisterResponse(BaseModel):
    api_key: str


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