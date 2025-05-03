from fastapi import APIRouter, HTTPException, status, Request
from app.models import ChatRequestModel, AdminModel, UserModel, CompanyModel
from shortuuid import uuid
from app.dependencies import Chat, Company, Admin
from . import logger

router = APIRouter()

@router.post("/chat/company/")
async def create_new_company(data: dict) -> CompanyModel:
    company = Company(data["name"])
    return {"name": company.name, "integration": None}


@router.post("/chat/company/admin")
async def create_new_admin(data: dict) -> AdminModel:
    admin = Admin(data["name"], key=uuid())
    return {"username": admin.name, "key": admin.key, "company": None}


@router.post("/chat/")
async def create_chat(data) -> dict:
    chat = Chat()
    logger.info("Создан новый чат:", chat.conversation, chat.chat_id)
    message = await chat.add_message("Здравствуйте!")
    # chat_id = await chat.new_chat(data.message)
    # logger.info("ID чата:", chat_id)
    logger.info("Ответ из чата:", message)
    return {"is_created": True}


# @router.post("/chat/configure/{chat_id}")
# async def configure_chat(data):
#     pass
#     return {"message": "Принято"}


# @router.post("/chat/{chat_id}")
# async def post_to_chat(data: ChatRequest) -> dict:
#     # chat.post()
#     return {"chat_id": "Отправить в чат"}
