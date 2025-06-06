from fastapi import Header, HTTPException, Depends
from sqlmodel import Session, select

from app import logger
from app.models import Company
from app.database import engine
from app.clients import redis


def get_company_session():
    with Session(engine) as session:
        yield session


async def get_redis_connection():
    try:
        return redis
    except Exception as e:
        logger.error(f"Error connecting to Redis: {e}")
        raise HTTPException(status_code=500, detail="Redis connection error")


def get_current_company(
    x_api_key: str = Header(...), session: Session = Depends(get_company_session)
) -> Company:
    company = session.exec(select(Company).where(Company.api_key == x_api_key)).first()
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return company
