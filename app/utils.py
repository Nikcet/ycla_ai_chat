import base64
from openai.lib.azure import AzureOpenAI
from openai import APIError, RateLimitError, InternalServerError
from pathlib import Path
from typing import List, Union
import docx2txt
from pypdf import PdfReader
from app import logger, settings
from uuid import uuid4
from fastapi import HTTPException
import json
from redis import asyncio as aioredis
import requests
from io import BytesIO

client = AzureOpenAI(
    api_key=settings.api_key,
    api_version=settings.embedding_model_api_version,
    azure_endpoint=settings.embedding_model_url,
)


def get_embedding(text: str) -> List[float]:
    """
    Generate an embedding for the given text with robust error handling.

    Returns:
        List[float]: The embedding for the input text.
    Raises:
        RuntimeError: If embedding generation fails after retries
    """
    if not isinstance(text, str):
        logger.error("Input text must be a string")
        raise TypeError("Input text must be a string")

    text = text.strip().strip("\n")
    if not text:
        logger.error("Empty text provided for embedding")
        raise ValueError("Input text is empty")

    try:
        logger.info(f"Generating embedding for text of length {len(text)}")
        response = client.embeddings.create(
            input=[text], model=settings.embedding_model_name
        )
        logger.info(
            f"Successfully generated embedding with {len(response.data[0].embedding)} dimensions"
        )
        return response.data[0].embedding

    except (RuntimeError, APIError, RateLimitError, InternalServerError) as e:
        logger.error(f"Embedding generation failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"Embedding generation failed: {str(e)}") from e
    except Exception as e:
        logger.critical(
            f"Critical error in embedding generation: {str(e)}", exc_info=True
        )
        raise


def chunk_text(text: str, size: int = 1000) -> List[str]:
    """
    Split the input text into chunks with validation
    """
    if not isinstance(text, str):
        logger.error("Non-string input received for chunking")
        raise TypeError("Input text must be a string")

    if not isinstance(size, int) or size <= 0:
        logger.error(f"Invalid chunk size: {size}")
        raise ValueError("Chunk size must be a positive integer")

    logger.info(f"Splitting text into {size} character chunks")
    chunks = [text[i : i + size] for i in range(0, len(text), size)]
    logger.info(f"Created {len(chunks)} chunks from text of length {len(text)}")
    return chunks


def extract_text_from_pdf(content: bytes) -> str:
    """
    Extract text from PDF with proper error handling
    """
    try:
        logger.info("Extracting text from PDF")
        reader = PdfReader(BytesIO(content))
        text = ""

        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            text += page_text
            logger.debug(f"Extracted {len(page_text)} characters from page {page_num}")

        cleaned_text = text.strip()
        logger.info(f"Successfully extracted {len(cleaned_text)} characters from PDF")
        return cleaned_text

    except Exception as e:
        logger.error(f"Error extracting PDF content: {str(e)}", exc_info=True)
        raise ValueError(f"PDF extraction failed: {str(e)}") from e


def extract_text_from_docx(content: bytes) -> str:
    """
    Extract text from DOCX with proper error handling
    """
    try:
        logger.info("Extracting text from DOCX")
        text = docx2txt.process(BytesIO(content)).strip()
        logger.info(f"Successfully extracted {len(text)} characters from DOCX")
        return text

    except Exception as e:
        logger.error(f"Error extracting DOCX content: {str(e)}", exc_info=True)
        raise ValueError(f"DOCX extraction failed: {str(e)}") from e


def extract_text(file_content: bytes, file_name: str) -> str:
    """
    Extract text from various file types with validation
    """
    logger.info(f"Starting text extraction for file: {file_name}")

    if not isinstance(file_content, bytes):
        logger.error("Input file must be bytes")
        raise TypeError("Input file must be bytes")

    ext = Path(file_name).suffix.lower()
    logger.debug(f"Detected file extension: {ext}")

    try:
        match ext:
            case ".pdf":
                return extract_text_from_pdf(file_content)
            case ".docx":
                return extract_text_from_docx(file_content)
            case _:
                logger.warning(f"Unsupported file type: {ext}")
                raise ValueError(f"Unsupported file type: {ext}")
    except ValueError as ve:
        raise ve
    except Exception as e:
        logger.error(
            f"Unexpected error during text extraction: {str(e)}", exc_info=True
        )
        raise ValueError(f"Text extraction failed: {str(e)}") from e


def create_batch(company_id: str, file_content: bytes, file_name: str, document_id: str) -> List[dict]:
    """
    Create document batch with comprehensive error handling
    """
    logger.info(f"Creating batch for company {company_id}, document {document_id}")

    if not all([company_id, file_content, file_name, document_id]):
        logger.error("Missing required parameters")
        raise ValueError("Missing required parameters for batch creation")

    try:
        text = extract_text(file_content=file_content, file_name=file_name)
        logger.info(f"Extracted {len(text)} characters from {file_name}")

        if not text:
            logger.warning("Empty text extracted from file")
            raise ValueError("No text extracted from file")

        chunks = chunk_text(text, int(settings.embedding_model_size))
        logger.info(f"Created {len(chunks)} chunks for document {file_name}")

        batch = []
        for i, chunk in enumerate(chunks):
            try:
                emb = get_embedding(chunk)
                doc_id = f"{company_id}-{uuid4()}"

                batch.append(
                    {
                        "id": doc_id,
                        "company_id": company_id,
                        "document_id": document_id,
                        "content": str(chunk),
                        "embedding": emb,
                    }
                )
                logger.debug(
                    f"Created chunk {i+1}/{len(chunks)} for document {document_id}"
                )

            except Exception as e:
                logger.error(f"Failed to process chunk {i+1}: {str(e)}", exc_info=True)

        logger.info(f"Successfully created batch with {len(batch)} documents")
        return batch

    except ValueError as ve:
        logger.error(f"Value error during batch creation: {str(ve)}")
        raise HTTPException(status_code=400, detail=f"Batch creation failed: {str(ve)}")
    except Exception as e:
        logger.error(f"Unexpected error during batch creation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def encode_document_key(key: str) -> str:
    """
    Encode document key with proper error handling
    """
    if not isinstance(key, str):
        logger.error("Non-string key attempted for encoding")
        raise TypeError("Key must be a string")

    try:
        encoded = base64.urlsafe_b64encode(key.encode()).decode("utf-8")
        logger.debug(f"Encoded document key: {key[:10]}... -> {encoded[:10]}...")
        return encoded
    except Exception as e:
        logger.error(f"Error encoding document key: {str(e)}", exc_info=True)
        raise ValueError(f"Document key encoding failed: {str(e)}") from e


async def get_redis_history(redis_client: aioredis.Redis, key: str) -> list:
    """
    Get chat history from Redis with error handling
    """
    if not redis_client:
        logger.error("Redis client not initialized")
        raise ValueError("Redis client is required")

    try:
        logger.debug(f"Fetching Redis history for key: {key}")
        history = await redis_client.lrange(key, 0, -1)

        if history:
            logger.info(f"Retrieved {len(history)} history items from Redis")
            return [json.loads(msg) for msg in history]

        logger.info("No history found in Redis")
        return []

    except aioredis.RedisError as re:
        logger.error(f"Redis connection error: {str(re)}", exc_info=True)
        raise HTTPException(status_code=503, detail="Redis service unavailable")
    except Exception as e:
        logger.error(f"Error processing Redis history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")


async def set_redis_history(
    redis_client: aioredis.Redis, key: str, *values: str
) -> None:
    """
    Set chat history in Redis with error handling
    """
    if not redis_client:
        logger.error("Redis client not initialized")
        raise ValueError("Redis client is required")

    if not values:
        logger.warning("No values provided for Redis history")
        return

    try:
        logger.debug(f"Saving {len(values)} items to Redis history")
        await redis_client.rpush(key, *values)
        await redis_client.ltrim(key, -10, -1)
        logger.info(f"Successfully saved {len(values)} items to Redis history")

    except aioredis.RedisError as re:
        logger.error(f"Redis connection error: {str(re)}", exc_info=True)
        raise HTTPException(status_code=503, detail="Redis service unavailable")
    except Exception as e:
        logger.error(f"Error saving to Redis history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save chat history")


def send_webhook(url: str, payload: dict):
    """
    Send webhook with error handling
    """
    if not url or not payload:
        logger.error("Missing required parameters for webhook")
        raise ValueError("URL and payload are required for webhook")

    try:
        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )
        if response.status_code < 300:
            logger.info(f"Webhook sent to {url}, status: {response.status_code}")
        else:
            logger.warning(f"Webhook failed with status code {response.status_code}")
    except requests.RequestException as re:
        logger.error(f"Webhook request error: {str(re)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send webhook")
    return response
