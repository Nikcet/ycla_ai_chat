from sqlmodel import create_engine
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from app import config, logger

settings = config.get_app_settings()

engine = create_engine("sqlite:///database.db")


search_client = SearchClient(
    endpoint=settings.search_endpoint,
    index_name=settings.search_index,
    credential=AzureKeyCredential(settings.search_admin_key),
)
logger.info(f"Create search client: {search_client}")
