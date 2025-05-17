from uuid import uuid4
# from shortuuid import uuid
from typing import Optional
# from pydantic import BaseModel, Field
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlmodel import SQLModel, Field, create_engine, Session, select

# Base = declarative_base()


class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    api_key: str = Field(index=True, unique=True, default=str(uuid4()))

# class CompanyModel(Base):
#     __tablename__ = "companies"
#     id = Column(String, primary_key=True, default=lambda: str(uuid4()))
#     name = Column(String)
#     api_key = Column(String, unique=True)


# class AdminModel(Base):
#     __tablename__ = "admins"
#     id = Column(String, primary_key=True, default=lambda: str(uuid4()))
#     username = Column(String)
#     company_id = Column(String, ForeignKey("companies.id"))


# class ChatModel(Base):
#     __tablename__ = "chats"
#     id = Column(String, primary_key=True, default=lambda: str(uuid4()))
#     company_id = Column(String, ForeignKey("companies.id"))
#     messages = Column(JSON)  # или отдельная таблица для сообщений


# class ChatRequestModel(BaseModel):
#     message: Optional[str] = None
#     chat_id: Optional[str] = None


# class ModelInfo(BaseModel):
#     model_from: Optional[str] = None
#     api_key: Optional[str] = None
#     model_name: Optional[str] = None
#     embedding_model_name: Optional[str] = None
#     temperature: float = 1.0
#     model_endpoint: Optional[str] = None
#     model_api_version: Optional[str] = None


# class VectorStorage(BaseModel):
#     provider_name: Optional[str] = None
#     api_key: Optional[str] = None
#     environment_name: Optional[str] = None
#     index_name: Optional[str] = None
#     name_space: Optional[str] = None
