from pydantic import BaseModel, Field
from typing import Optional, List, Dict
# from datetime import datetime
# from sqlmodel import SQLModel, Field, create_engine, Session, select


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


# class Company(SQLModel, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     name: str = Field(index=True)
#     api_key: str = Field(index=True, unique=True)

# # Для Company
# class CompanyCreate(BaseModel):
#     name: str = Field(..., max_length=100)


# class CompanyResponse(CompanyCreate):
#     id: str
#     name: str = Field(..., max_length=100)
#     created_at: datetime

#     class Config:
#         orm_mode = True


# # Для Admin
# class AdminCreate(BaseModel):
#     username: str = Field(..., min_length=3, max_length=50)
#     company_id: str


# class AdminResponse(AdminCreate):
#     id: str
#     created_at: datetime

#     class Config:
#         orm_mode = True


# # Для Chat
# class Message(BaseModel):
#     content: str
#     role: str


# class ChatCreate(BaseModel):
#     company_id: str
#     initial_message: Optional[str] = None  # если нужно сразу создать первое сообщение


# class ChatResponse(BaseModel):
#     id: str
#     company_id: str
#     messages: Dict[Message]  # или Dict если предпочитаете JSON-объект
#     created_at: datetime
#     updated_at: datetime

#     class Config:
#         orm_mode = True


# class ApiKey(CompanyResponse):
#     api_key: str
