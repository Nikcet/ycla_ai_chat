from sqlmodel import create_engine
from azure.core.credentials import AzureKeyCredential
# from azure.search.documents import SearchClient
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    CorsOptions,
    SearchIndex,
    ScoringProfile,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    LexicalAnalyzerName,
)

from app import config, logger

settings = config.get_app_settings()

engine = create_engine(settings.sqlite_url)


def get_search_client(index_name: str = settings.search_index):
   """
   Get a search client.

   Args:
       index_name (str): The name of the search index.

   Returns:
       SearchClient: The search client object.

   Raises:
       Exception: If the search client cannot be created.
   """
   client = SearchClient(
       endpoint=settings.search_endpoint,
       index_name=index_name,
       credential=AzureKeyCredential(settings.search_admin_key),
   )
   if client is None:
       raise Exception("Failed to create search client.")

   logger.info("Created search client.")
   return client


def get_async_search_client(index_name: str = settings.search_index):
   """
   Get a search client.

   Args:
       index_name (str): The name of the search index.

   Returns:
       SearchClient: The search client object.

   Raises:
       Exception: If the search client cannot be created.
   """
   client = SearchClient(
       endpoint=settings.search_endpoint,
       index_name=index_name,
       credential=AzureKeyCredential(settings.search_admin_key),
   )
   if client is None:
       raise Exception("Failed to create search client.")

   logger.info("Created search client.")
   return client


def create_search_client(company_id: int):
   """
   Create a search client.

   Args:
       company_id (int): The ID of the company.

   Returns:
       SearchClient: The search client object.

   Raises:
       Exception: If the search client cannot be created.
   """
   client = SearchIndexClient(
       endpoint=settings.search_endpoint,
       credential=AzureKeyCredential(settings.search_admin_key),
   )
   name = settings.search_index + "-ai-chat-" + str(company_id)
   fields = [
       SimpleField(name="id", type=SearchFieldDataType.String, key=True),
       SearchableField(
           name="company_id", type=SearchFieldDataType.String, filterable=True
       ),
       SearchableField(
           name="document_id", type=SearchFieldDataType.String, filterable=True
       ),
       SearchableField(
           name="content",
           type=SearchFieldDataType.String,
           filterable=True,
           analyzer_name=LexicalAnalyzerName.STANDARD_LUCENE,
       ),
       SearchableField(
           name="embeddings",
           type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
       ),
   ]
   cors_options = CorsOptions(allowed_origins=["*"], max_age_in_seconds=3600)
   scoring_profiles: list[ScoringProfile] = []
   index = SearchIndex(
       name=name,
       fields=fields,
       scoring_profiles=scoring_profiles,
       cors_options=cors_options,
   )
   result = client.create_index(index)
   if result is None:
       raise Exception("Failed to create search client.")

   logger.info("Created admin client.")
   return get_search_client(name)



# search_client = get_search_client()
search_client = get_async_search_client()
# admin_client = create_search_client()
