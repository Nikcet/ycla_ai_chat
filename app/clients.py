from openai import AsyncOpenAI
from openai.lib.azure import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from redis import asyncio as aioredis
from azure.search.documents import SearchClient
from sqlmodel import create_engine

from app import settings, logger

try:
    azure_client = AsyncAzureOpenAI(
        api_key=settings.api_key,
        api_version=settings.api_version,
        azure_endpoint=settings.endpoint,
    )
except Exception as e:
    logger.error(f"Error initializing Azure client: {e}")

try:
    deepseek_client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_url,
    )
except Exception as e:
    logger.error(f"Error initializing DeepSeek client: {e}")

try:
    redis = aioredis.from_url(
        url=f"redis://{settings.redis_host}:{settings.redis_port}/0",
        decode_responses=True,
    )
except Exception as e:
    logger.error(f"Error connecting to Redis: {e}")

try:
    search_client = SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index,
        credential=AzureKeyCredential(settings.search_admin_key),
    )
except Exception as e:
    logger.error(f"Error connecting to Azure Cognitive Search: {e}")


try:
    engine = create_engine(
        settings.pg_url,
        echo=True,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=10,
        max_overflow=10,
        pool_size=20,
    )
except Exception as e:
    logger.error(f"Error connecting to PostgreSQL: {e}")
