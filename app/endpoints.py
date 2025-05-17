from fastapi import APIRouter, HTTPException, status, Request, Depends
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.database import AsyncSessionLocal
# from app.models import AdminModel, CompanyModel
from shortuuid import uuid
from uuid import uuid4

# from app.dependencies import Chat, Company, Admin
from . import logger

from app.schemas import (
    RegisterResponse,
    RegisterRequest,
    UploadRequest,
    ChatResponse,
    ChatRequest,
)
from app.models import Company
from app.dependencies import get_session, get_current_company
from app.database import engine, search_client
from app.utils import get_embedding, chunk_text
from app.config import get_app_settings

from sqlmodel import Session, select
import openai

settings = get_app_settings()
router = APIRouter()

openai.api_type = settings.api_type
openai.api_base = settings.endpoint
openai.api_version = settings.api_version
openai.api_key = settings.api_key


@router.post("/admin/register", response_model=RegisterResponse)
def register_company(req: RegisterRequest, session: Session = Depends(get_session)):
    # api_key = uuid4()
    company = Company(name=req.name)
    session.add(company)
    session.commit()
    return RegisterResponse(api_key=company.api_key)


@router.post("/admin/upload", dependencies=[Depends(get_current_company)])
def upload_documents(
    req: UploadRequest, company: Company = Depends(get_current_company)
):
    batch = []
    for doc in req.documents:
        for chunk in chunk_text(doc):
            emb = get_embedding(chunk)
            batch.append(
                {
                    "id": f"{company.id}-{uuid()}",
                    "company_id": company.id,
                    "content": chunk,
                    "embedding": emb,
                }
            )
    search_client.upload_documents(documents=batch)
    return {"indexed": len(batch)}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, company: Company = Depends(get_current_company)):
    q_emb = get_embedding(req.question)
    results = search_client.search(
        search_text="*",
        vector={"value": q_emb, "fields": "embedding", "k": 3},
        filter=f"company_id eq {company.id}",
    )
    context = "\n".join([doc["content"] for doc in results])
    messages = [
        {
            "role": "system",
            "content": "Используй только предоставленный контекст для ответа.",
        },
        {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}"},
    ]
    resp = openai.ChatCompletion.create(
        model=settings.model_name, messages=messages, temperature=0.2
    )
    return ChatResponse(answer=resp.choices[0].message.content)


# @router.get("/company/all")
# async def get_all_companies():
#     # Запрос к БД на вывод всех компаний
#     return {"companies": []}


# @router.get("/company/{company_id}")
# async def get_company(company_id: str):
#     logger.info(company_id)
#     # Запрос к БД на поиск компании
#     return {"name", "Ycla Company"}


# @router.post("/company")
# async def create_new_company(data: dict) -> CompanyModel:
#     logger.info(data)
#     # Запрос к БД на создание компании
#     return {"name": "name", "integration": None}


# @router.delete("/company/{company_id}")
# async def remove_company(company_id: str):
#     logger.info(company_id)
#     # Запрос к БД на удаление компании
#     return {"is_removed", True}


# @router.put("/company/{company_id}")
# async def update_company(data: dict):
#     logger.info(data)
#     # Запрос к БД на обновление компании
#     return {"name", "Ycla Company"}


# @router.get("/company/{company_id}/admin/{admin_id}")
# async def get_admin(company_id: str, admin_id: str):
#     logger.info(company_id, admin_id)
#     # Запрос к БД на поиск админа
#     return {"username": "username"}


# @router.post("/company/{company_id}/admin")
# async def create_new_admin(company_id: str, data: dict) -> AdminModel:
#     logger.info(company_id)
#     logger.info(data)
#     # Запрос к БД на создание нового админа
#     return {
#         "username": "user",
#         "key": str(uuid()),
#         "company_id": company_id,
#     }


# @router.put("/company/{company_id}/admin/{admin_id}")
# async def update_admin(company_id: str, admin_id: str):
#     logger.info(company_id)
#     logger.info(admin_id)
#     # Запрос к БД на обновление админа
#     return {"username": "username", "company_id": company_id, "admin_id": admin_id}


# @router.delete("/company/{company_id}/admin/{admin_id}")
# async def remove_admin(company_id: str, admin_id: str):
#     logger.info(company_id)
#     logger.info(admin_id)
#     # Запрос к БД на удаление админа
#     return {"is_removed", True}


# @router.post("/company/{company_id}/chat")
# async def create_new_chat(company_id: str, data: dict):
#     logger.info(company_id)
#     logger.info(data)
#     # Запрос к БД на создание нового чата
#     return {"company_id": company_id, "data": data}


# @router.get("/company/{company_id}/chat/{chat_id}")
# async def get_chat(chat_id: str):
#     logger.info(chat_id)
#     # Запрос к БД на поиск чата с таким chat_id
#     return {"messages": []}


# @router.delete("/company/{company_id}/chat/{chat_id}")
# async def remove_chat(chat_id: str):
#     logger.info(chat_id)
#     # Запрос к БД на удаление чата с указанным id
#     return {"is_removed": True}


# @router.post("/chat/test")
# async def make_query(data: dict[str, str]):
# answer = await chat.add_message(data["message"])
# return {"message": answer}
