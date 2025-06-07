from fastapi import Header, HTTPException, Depends, Request
from sqlmodel import Session, select
from redis import asyncio as aioredis

from app import logger, settings
from app.models import Company
from app.database import decode_jwt, create_jwt
from app.clients import redis, search_client, engine


def get_company_session():
    with Session(engine) as session:
        yield session


def get_redis_connection():
    try:
        return redis
    except Exception as e:
        logger.error(f"Error connecting to Redis: {e}")
        raise HTTPException(status_code=500, detail="Redis connection error")


def get_search_client():
    """
    Get a search client.

    Returns:
        SearchClient: The search client object.

    Raises:
        Exception: If the search client cannot be created.
    """
    try:
        return search_client
    except Exception as e:
        logger.error(f"Error connecting to Azure AI Search: {e}")
        raise HTTPException(status_code=500, detail="Azure AI Search connection error")


def get_current_company(
    x_api_key: str = Header(...), session: Session = Depends(get_company_session)
) -> Company:
    company = session.exec(select(Company).where(Company.api_key == x_api_key)).first()
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return company


async def get_session_from_jwt(
    request: Request,
    company: Company = Depends(get_current_company),
    redis: aioredis.Redis = Depends(get_redis_connection),
) -> tuple[str, str]:
    authorization = request.headers.get("Authorization")

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = decode_jwt(token)
            session_id = payload["session_id"]

            session_data = await redis.get(f"session:{session_id}")
            if not session_data:
                new_token, new_session_id = create_jwt(company.id)
                await redis.setex(f"session:{new_session_id}", settings.session_ttl, company.id)
                return new_session_id, new_token

            return session_id, token
        except ValueError:
            new_token, new_session_id = create_jwt(company.id)
            await redis.setex(f"session:{new_session_id}", settings.session_ttl, company.id)
            return new_session_id, new_token
    else:
        new_token, new_session_id = create_jwt(company.id)
        await redis.setex(f"session:{new_session_id}", settings.session_ttl, company.id)
        return new_session_id, new_token
