# import os
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# from sqlalchemy.ext.declarative import declarative_base

# from collections.abc import AsyncGenerator

# from fastapi.encoders import jsonable_encoder
# from sqlalchemy.orm import sessionmaker

from sqlmodel import create_engine

from azure.core.credentials import AzureKeyCredential

# Используем Azure AI Search SDK
from azure.search.documents import SearchClient


from app import config, logger

settings = config.get_app_settings()

engine = create_engine("sqlite:///database.db")



search_client = SearchClient(
    endpoint=settings.search_endpoint,
    index_name=settings.search_index,
    credential=AzureKeyCredential(settings.search_query_key),
)
logger.info(f"Create search client: {search_client}")

# from azure.search.documents.indexes import SearchIndexClient
# from azure.search.documents.indexes.models import (
#     SearchIndex,
#     SimpleField,
#     SearchField,
#     SearchableField,
#     SearchFieldDataType,
#     VectorSearch,
#     VectorSearchAlgorithmConfiguration,
#     VectorSearchProfile,
# )
# from azure.core.exceptions import HttpResponseError

# admin_client = SearchIndexClient(
#     endpoint=settings.search_endpoint,
#     credential=AzureKeyCredential(settings.search_admin_key),
# )

# def create_index():
#     vector_search = VectorSearch(
#         algorithm_configurations=[
#             VectorSearchAlgorithmConfiguration(name="cosine-config", kind="cosine")
#         ],
#         profiles=[
#             VectorSearchProfile(
#                 name="default", algorithm_configuration_name="cosine-config"
#             )
#         ]
#     )
    
#     fields = [
#         SimpleField(name="id", type=SearchFieldDataType.String, isKey=True),
#         SimpleField(
#             name="company_id",
#             type=SearchFieldDataType.Int32,
#             isFilterable=True,
#             isFacetable=True,
#         ),
#         SearchableField(name="content", type=SearchFieldDataType.String),
#         SearchField(
#             name="embedding",
#             type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
#             isSearchable=True,
#             vector_search_dimensions=150,
#             vector_search_configuration="cosine-config",
#             vector_search_profile="default"
#         ),
#     ]
#     index = SearchIndex(
#         name=settings.search_index, fields=fields, vector_search=vector_search
#     )
#     return index

# try:
#     admin_client.get_index(settings.search_index)
# except HttpResponseError as e:
#     if e.status_code == 403:
#         raise RuntimeError("Отказано в доступе: неверный AZURE_SEARCH_ADMIN_KEY")
#     if e.status_code == 404:
#         admin_client.create_index(create_index())
#     else:
#         raise



# global_settings = config.get_settings()
# url = global_settings.asyncpg_url
# logger.info(url)
# engine = create_async_engine(
#     url,
#     future=True,
#     echo=True,
#     json_serializer=jsonable_encoder,
# )

# # expire_on_commit=False will prevent attributes from being expired
# # after commit.
# AsyncSessionFactory = async_sessionmaker(
#     engine, autoflush=False, expire_on_commit=False, class_=AsyncSession
# )


# # Dependency
# async def get_db() -> AsyncGenerator:
#     async with AsyncSessionFactory() as session:
#         logger.debug(f"ASYNC Pool: {engine.pool.status()}")
#         yield session
