import os
from dotenv import load_dotenv
from functools import lru_cache

from pydantic_settings import BaseSettings

from app import logger
load_dotenv()

class Database_settings(BaseSettings):
    pg_user: str = os.getenv("SQL_DB_USER")
    pg_pass: str = os.getenv("SQL_DB_PASSWORD")
    pg_host: str = os.getenv("SQL_DB_HOST")
    pg_port: str = os.getenv("SQL_DB_PORT", "5432")
    pg_database: str = os.getenv("SQL_DB_NAME")
    pg_driver: str = os.getenv("SQL_DB_DRIVER", "psycopg2")
    
    @property
    def pg_url(self):
        return f"postgresql+{self.pg_driver}://{self.pg_user}:{self.pg_pass}@{self.pg_host}:{self.pg_port}/{self.pg_database}"


@lru_cache
def get_db_settings():
    """Get settings"""
    logger.info("Loading config settings from the environment...")
    return Database_settings()


class App_settings(BaseSettings):
    endpoint: str = os.getenv("AZURE_ENDPOINT_URL", "")
    api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    model_name: str = os.getenv("AZURE_MODEL_NAME", "o3-mini")
    deployment_name: str = os.getenv("AZURE_DEPLOYMENT_NAME", "o3-mini")

    deepseek_url: str = os.getenv("DEEPSEEK_API_URL", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_API_MODEL", "")

    embedding_model_name: str = os.getenv(
        "AZURE_EMBEDDING_MODEL_NAME", "text-embedding-3-large"
    )
    embedding_model_url: str = os.getenv("AZURE_EMBEDDING_URL", "")
    embedding_model_deployment: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "")
    embedding_model_api_version: str = os.getenv("AZURE_EMBEDDING_API_VERSION", "")
    embedding_model_size: str = os.getenv(
        "AZURE_EMBEDDING_MODEL_SIZE", "3072"
    )  # The size of embedding model 'text-embedding-3-large' that is by default

    search_endpoint: str = os.getenv("VECTOR_STORE_URL", "")
    search_password: str = os.getenv("VECTOR_STORE_PASSWORD", "")
    search_index: str = os.getenv("VECTOR_STORE_INDEX_NAME", "searcher")
    search_admin_key: str = os.getenv("VECTOR_STORE_ADMIN_KEY", "")
    search_query_key: str = os.getenv("VECTOR_STORE_USER_KEY", "")

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: str = os.getenv("REDIS_PORT", "6379")
    redis_password: str = os.getenv("REDIS_PASSWORD", "")

    sqlite_url: str = os.getenv("SQLITE_URL", "")
    pg_url: str = Database_settings().pg_url
    
    nearest_neighbors: int = 5
    
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "")
    session_ttl: int = 86400
    
    supported_extensions: set[str] = {".pdf", ".docx"}
    max_file_size: int = 1024 * 1024 * 100 # 100 MB

@lru_cache
def get_app_settings():
    """Get settings"""
    logger.info("Loading config app settings from the environment...")
    return App_settings()
