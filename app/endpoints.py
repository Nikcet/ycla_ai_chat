from fastapi import APIRouter, HTTPException, status, Request
from app.models import ChatRequestModel, AdminModel, UserModel, CompanyModel
from shortuuid import uuid
from app.dependencies import Chat, Company, Admin
from . import logger

router = APIRouter()


@router.get("/company/all")
async def get_all_companies():
    # Запрос к БД на вывод всех компаний
    return {"companies": []}


@router.get("/company/{company_id}")
async def get_company(company_id: str):
    logger.info(company_id)
    # Запрос к БД на поиск компании
    return {"name", "Ycla Company"}


@router.post("/company")
async def create_new_company(data: dict) -> CompanyModel:
    logger.info(data)
    # Запрос к БД на создание компании
    return {"name": "name", "integration": None}


@router.delete("/company/{company_id}")
async def remove_company(company_id: str):
    logger.info(company_id)
    # Запрос к БД на удаление компании
    return {"is_removed", True}


@router.put("/company/{company_id}")
async def update_company(data: dict):
    logger.info(data)
    # Запрос к БД на обновление компании
    return {"name", "Ycla Company"}


@router.get("/company/{company_id}/admin/{admin_id}")
async def get_admin(company_id: str, admin_id: str):
    logger.info(company_id, admin_id)
    # Запрос к БД на поиск админа
    return {"username": "username"}


@router.post("/company/{company_id}/admin")
async def create_new_admin(company_id: str, data: dict) -> AdminModel:
    logger.info(company_id)
    logger.info(data)
    # Запрос к БД на создание нового админа
    return {
        "username": "user",
        "key": str(uuid()),
        "company_id": company_id,
    }


@router.put("/company/{company_id}/admin/{admin_id}")
async def update_admin(company_id: str, admin_id: str):
    logger.info(company_id)
    logger.info(admin_id)
    # Запрос к БД на обновление админа
    return {"username": "username", "company_id": company_id, "admin_id": admin_id}


@router.delete("/company/{company_id}/admin/{admin_id}")
async def remove_admin(company_id: str, admin_id: str):
    logger.info(company_id)
    logger.info(admin_id)
    # Запрос к БД на удаление админа
    return {"is_removed", True}


@router.post("/company/{company_id}/chat")
async def create_new_chat(company_id: str, data: dict):
    logger.info(company_id)
    logger.info(data)
    # Запрос к БД на создание нового чата
    return {"company_id": company_id, "data": data}


@router.get("/company/{company_id}/chat/{chat_id}")
async def get_chat(chat_id: str):
    logger.info(chat_id)
    # Запрос к БД на поиск чата с таким chat_id
    return {"messages": []}


@router.delete("/company/{company_id}/chat/{chat_id}")
async def remove_chat(chat_id: str):
    logger.info(chat_id)
    # Запрос к БД на удаление чата с указанным id
    return {"is_removed": True}


# @router.post("/chat/test")
# async def make_query(data: dict[str, str]):
# answer = await chat.add_message(data["message"])
# return {"message": answer}
