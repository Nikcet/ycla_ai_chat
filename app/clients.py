from openai import AsyncOpenAI
from openai.lib.azure import AsyncAzureOpenAI
from app import settings, logger
from redis import asyncio as aioredis

azure_client = AsyncAzureOpenAI(
    api_key=settings.api_key,
    api_version=settings.api_version,
    azure_endpoint=settings.endpoint,
)
if azure_client:
    logger.info("Azure OpenAI client initialized successfully")
else:
    logger.error("Azure OpenAI client initialization failed")

deepseek_client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_url,
)

if deepseek_client:
    logger.info("DeepSeek client initialized successfully")
else:
    logger.error("DeepSeek client initialization failed")

logger.info(settings.redis_port)
redis = aioredis.from_url(
    url=f"redis://{settings.redis_host}:{settings.redis_port}/0", decode_responses=True
)

if redis:
    logger.info("redis client initialized successfully")
else:
    logger.error("redis client initialization failed")
