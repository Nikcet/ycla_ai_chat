import os
from openai import AzureOpenAI

# from openai.types.embeddings import Embedding
from pathlib import Path
from typing import List, Union
import docx2txt
from pypdf import PdfReader
from app.config import get_app_settings
from app import logger

settings = get_app_settings()

client = AzureOpenAI(
    api_key=settings.api_key,
    api_version=settings.embedding_model_api_version,
    azure_endpoint=settings.embedding_model_url,
)


async def get_embedding(text: str) -> List[float]:
    if not isinstance(text, str):
        raise TypeError("Input text must be a string")
    text = text.strip().strip("\n")
    if not text:
        raise ValueError("Input text is empty")
    try: 
        response = await client.embeddings.create(
            input=[text], model=settings.embedding_model_name
        )
        return response.data[0].embedding
    except Exception as e:
        raise RuntimeError(f"Embedding generation failed: {e}")


def chunk_text(text: str, size: int = 1000) -> List[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def extract_text_from_pdf(file_path: Union[str, Path]) -> str:
    file_path = Path(file_path)
    reader = PdfReader(str(file_path))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def extract_text_from_docx(file_path: Union[str, Path]) -> str:
    file_path = Path(file_path)
    return docx2txt.process(str(file_path)).strip()


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Неподдерживаемый тип файла: {ext}")
