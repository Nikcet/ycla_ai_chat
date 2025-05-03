from uuid import uuid4
from shortuuid import uuid
from typing import Optional
from pydantic import BaseModel, Field


class CompanyModel(BaseModel):
    """
    Модель компании

    Поля:
    - id (str): Уникальный UUID компании (генерируется shortuuid)
    - name (str): Название компании (обязательное)
    - integration (Optional[str]): Данные интеграции
    """

    id: str = Field(
        default_factory=lambda: uuid(),
        description="Уникальный UUID компании",
        primary_key=True,
    )
    name: str = Field(..., max_length=100, description="Название компании")
    integration: Optional[str] = Field(
        default=None, max_length=255, description="Конфигурация интеграции"
    )


class AdminModel(BaseModel):
    """
    Модель администратора с привязкой к компании

    Поля:
    - id (str): UUID администратора (генерируется shortuuid)
    - username (str): Логин (уникальный, макс. 255 символов)
    - key (str): Токен доступа (генерируется при создании)
    - company_id (Optional[str]): Ссылка на UUID компании из CompanyModel
    """

    id: str = Field(
        default_factory=lambda: uuid(), description="Уникальный UUID администратора"
    )
    username: str = Field(
        ..., max_length=255, unique=True, description="Уникальное имя пользователя"
    )
    key: str = Field(
        default_factory=lambda: str(uuid()), description="API-ключ доступа"
    )
    company_id: Optional[str] = Field(
        default=None,
        foreign_key="company.id",
        description="Внешний ключ к таблице компаний",
    )


class UserModel(BaseModel):
    """
    Модель пользователя для хранения в PostgreSQL

    Поля:
    - id (str): UUID пользователя (генерируется uuid4)
    - username (str): Логин (уникальный, макс. 255 символов)
    - key (str): Токен доступа (генерируется при создании)
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()), description="Уникальный UUID пользователя"
    )
    username: str = Field(
        ..., max_length=255, unique=True, description="Имя пользователя"
    )
    key: str = Field(
        default_factory=lambda: str(uuid4()), description="Токен авторизации"
    )


class ChatRequestModel(BaseModel):
    message: Optional[str] = None
    chat_id: Optional[str] = None


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
