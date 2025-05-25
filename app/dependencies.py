from fastapi import Header, HTTPException, Depends
from uuid import uuid4
from sqlmodel import Session, select
from typing import List

from app.models import Company
from app.config import get_app_settings
from app.database import engine
from app.utils import get_embedding, chunk_text, extract_text
from app.schemas import UploadRequest

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

# TODO: засунуть в задачу
async def create_batch(req: UploadRequest, company: Company, file_path: str) -> List[dict]:
    batch = []
    try:
        text = extract_text(file_path)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Ошибка чтения файла '{file_path}': {e}"
        )

    for chunk in chunk_text(text):
        emb = await get_embedding(chunk)
        batch.append(
            {
                "id": f"{company.id}-{uuid4()}",
                "company_id": int(company.id),
                "content": str(chunk),
                "embedding": [
                    float(x) for x in emb
                ],  # TODO: пока работает так, надо отрефакторить
            }
        )
    return batch
