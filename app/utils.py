import openai
from typing import List, Optional
from app.config import get_app_settings

settings = get_app_settings()


def get_embedding(text: str) -> List[float]:
    resp = openai.Embedding.create(input=text, model=settings.embedding_model_name)
    return resp.data[0].embedding


def chunk_text(text: str, size: int = 1000) -> List[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]