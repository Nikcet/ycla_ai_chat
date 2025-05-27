from pydantic import BaseModel
from typing import List


class RegisterRequest(BaseModel):
    name: str


class RegisterResponse(BaseModel):
    api_key: str


class UploadRequest(BaseModel):
    documents: List[str]


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
