from fastapi import Header, HTTPException, Depends

from sqlmodel import Session, select

from app.models import Company
from app.config import get_app_settings
from app.database import engine

app_settings = get_app_settings()


def get_session():
    with Session(engine) as session:
        yield session


def get_current_company(
    x_api_key: str = Header(...), session: Session = Depends(get_session)
) -> Company:
    company = session.exec(select(Company).where(Company.api_key == x_api_key)).first()
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return company

