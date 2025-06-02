import os

from functools import lru_cache

from pydantic_settings import BaseSettings

from app import logger


class Database_settings(BaseSettings):
    """

    BaseSettings, from Pydantic, validates the data so that when we create an instance of Settings,
     environment and testing will have types of str and bool, respectively.

    Parameters:
    pg_user (str):
    pg_pass (str):
    pg_database: (str):
    pg_test_database: (str):
    asyncpg_url: AnyUrl:
    asyncpg_test_url: AnyUrl:

    Returns:
    instance of Settings

    """

    pg_user: str = os.getenv("SQL_DATABASE_USER", "")
    pg_pass: str = os.getenv("SQL_DATABASE_PASSWORD", "")
    pg_host: str = os.getenv("SQL_DATABASE_HOST", "")
    pg_port: str = os.getenv("SQL_DATABASE_PORT", "")
    pg_database: str = os.getenv("SQL_DATABASE_NAME", "")
    pg_driver: str = "+" + os.getenv("SQL_DATABASE_DRIVER", "")
    asyncpg_url: str = (
        f"postgresql{pg_driver}://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_database}"
    )

    # jwt_secret_key: str = os.getenv("SECRET_KEY", "")
    # jwt_algorithm: str = os.getenv("ALGORITHM", "")
    # jwt_access_toke_expire_minutes: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1)


@lru_cache
def get_settings():
    """Get settings"""
    logger.info("Loading config settings from the environment...")
    return Database_settings()


class App_settings(BaseSettings):
    api_type: str = "azure"
    endpoint: str = os.getenv("AZURE_ENDPOINT_URL", "")
    api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    model_name: str = os.getenv("AZURE_MODEL_NAME", "o3-mini")
    deployment_name: str = os.getenv("AZURE_DEPLOYMENT_NAME", "o3-mini")

    embedding_model_name: str = os.getenv(
        "AZURE_EMBEDDING_MODEL_NAME", "text-embedding-3-large"
    )
    embedding_model_url: str = os.getenv("AZURE_EMBEDDING_URL", "")
    embedding_model_deployment: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "")
    embedding_model_api_version: str = os.getenv("AZURE_EMBEDDING_API_VERSION", "")
    embedding_model_size: str = os.getenv("AZURE_EMBEDDING_MODEL_SIZE", "3072")

    search_endpoint: str = os.getenv("VECTOR_STORE_URL", "")
    search_password: str = os.getenv("VECTOR_STORE_PASSWORD", "")
    search_index: str = os.getenv("VECTOR_STORE_INDEX_NAME", "searcher")
    search_admin_key: str = os.getenv("VECTOR_STORE_ADMIN_KEY", "")
    search_query_key: str = os.getenv("VECTOR_STORE_USER_KEY", "")

    redis_host: str = os.getenv("REDIS_HOST")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

    sqlite_url: str = os.getenv("SQLITE_URL")
    
    nearest_neighbors: int = 5


@lru_cache
def get_app_settings():
    """Get settings"""
    logger.info("Loading config app settings from the environment...")
    return App_settings()
