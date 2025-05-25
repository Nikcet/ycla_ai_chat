from fastapi import APIRouter, HTTPException, Depends
from azure.search.documents.models import VectorizedQuery
from uuid import uuid4
from sqlmodel import Session
from openai.lib.azure import AzureOpenAI


from app.schemas import (
    RegisterResponse,
    RegisterRequest,
    UploadRequest,
    ChatResponse,
    ChatRequest,
)
from app import logger
from app.models import Company
from app.dependencies import get_session, get_current_company, create_batch
from app.database import search_client
from app.utils import get_embedding
from app.config import get_app_settings


settings = get_app_settings()
router = APIRouter()

client = AzureOpenAI(
    api_key=settings.api_key,
    api_version=settings.api_version,
    azure_endpoint=settings.endpoint,
)


@router.post("/register", response_model=RegisterResponse)
async def register_company(
    req: RegisterRequest, session: Session = Depends(get_session)
):
    company = Company(name=req.name)
    await session.add(company)
    session.commit()
    return RegisterResponse(api_key=company.api_key)


@router.post("/upload", dependencies=[Depends(get_current_company)])
async def upload_documents(
    req: UploadRequest, company: Company = Depends(get_current_company)
):
    for file_path in req.documents:
        batch = await create_batch(file_path, company, file_path)
        # TODO: Поместить в задачу
        search_client.upload_documents(documents=batch)

    return {"indexed": len(batch)}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, company: Company = Depends(get_current_company)):
    q_emb = await get_embedding(req.question)
    vectorized_query = VectorizedQuery(
        vector=q_emb,
        k_nearest_neighbors=3,
        fields="embedding",
    )
    results = search_client.search(
        search_text="*",
        vector_queries=[vectorized_query],
        filter=f"company_id eq {company.id}",
    )

    # TODO: Реализовать асинхронный поиск в БД

    context = "\n".join([doc["content"] for doc in results])
    messages = [
        {
            "role": "system",
            "content": "Используй только предоставленный контекст для ответа.",
        },
        {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос:\n{req.question}"},
    ]

    response = client.chat.completions.create(
        model=settings.model_name,
        messages=messages,
        stream=False,
    )
    return ChatResponse(answer=response.choices[0].message.content)