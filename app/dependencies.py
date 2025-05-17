# import os
# from uuid import uuid4

# from openai.lib.azure import AzureOpenAI
# from dotenv import load_dotenv
# from loguru import logger
# from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
# from langchain_community.vectorstores.azuresearch import AzureSearch
# from langchain_community.document_loaders import TextLoader
# from langchain_text_splitters import CharacterTextSplitter
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from fastapi import FastAPI, Header, HTTPException, Depends

from sqlmodel import Session, select

from app.models import Company
from app.config import get_app_settings
from app.database import engine

app_settings = get_app_settings()


def get_session():
    with Session(engine) as session:
        yield session


def get_current_company(
    x_api_key: str = Header(...), session: Session = Depends(get_session)
) -> Company:
    company = session.exec(select(Company).where(Company.api_key == x_api_key)).first()
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return company


# if not load_dotenv():
#     logger.error("Install dotenv and create a '.env' file.")
#     raise ConnectionError("Install dotenv and/or create a '.env' file.")

# try:
#     AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
#     AZURE_OPENAI_API_URL = os.environ["AZURE_OPENAI_API_URL"]
#     AZURE_ENDPOINT_URL = os.environ["AZURE_ENDPOINT_URL"]
#     AZURE_DEPLOYMENT_NAME = os.environ["AZURE_DEPLOYMENT_NAME"]
#     AZURE_OPENAI_API_VERSION = os.environ["AZURE_OPENAI_API_VERSION"]
#     # VECTOR_STORE_ADDRESS = os.environ["VECTOR_STORE_ADDRESS"]
#     # VECTOR_STORE_PASSWORD = os.environ["VECTOR_STORE_PASSWORD"]
#     AZURE_MODEL_NAME = os.environ["AZURE_MODEL_NAME"]
# except Exception as e:
#     logger.error(f"Check the env variables. {e}")
#     raise


# class Company:
#     def __init__(self, name, integration=None):
#         self.name = name
#         self.integration = integration
#         # self.active_chats: dict[str, "Chat"] = {}

#         # Нужна модель для эмбеддингов (например, text-embedding-ada-002). Преобразует текст в числовые векторы (эмбеддинги)
#         # На выходе — массив чисел (например, 1536 измерений для ada-002).
#         # self.embeddings: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
#         #     azure_endpoint=ENDPOINT,
#         #     api_key=SECRET_KEY,
#         #     api_version=API_VERSION,
#         #     azure_deployment=DEPLOYMENT,
#         # )
#         # self.vector_store: AzureSearch = AzureSearch(
#         #     azure_search_endpoint=VECTOR_STORE_ADDRESS,
#         #     azure_search_key=VECTOR_STORE_PASSWORD,
#         #     index_name="test-index",
#         #     embedding_function=self.embeddings.embed_query,
#         #     additional_search_client_options={"retry_total": 4},
#         # )

#     def load(self):
#         loader = TextLoader("testText.txt", encoding="utf-8")
#         documents = loader.load()
#         text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
#         docs = text_splitter.split_documents(documents)
#         self.vector_store.add_documents(documents=docs)

#     def test_query_to_vbd(self):
#         docs = self.vector_store.similarity_search(
#             query="Кто такой Илон Маск?", k=3, search_type="similarity"
#         )
#         return docs[0].page_content


# class Admin:
#     def __init__(self, name, key):
#         self.name = name
#         self.key = key
#         self.company = None


# class Chat:
#     def __init__(self):
#         # super().__init__()
#         self.chat_id: str = uuid4()
#         self.chat = AzureChatOpenAI(
#             azure_deployment=app_settings.deployment_name,
#             azure_endpoint=app_settings.endpoint,
#             api_version=app_settings.api_version,
#             max_retries=2,
#             timeout=None,
#         )
#         self.messages = []
#         self.prompt_template = ChatPromptTemplate.from_messages(
#             [
#                 ("system", "Ты полезный ассистент, который помогает программировать и тестировать RAG систему."),
#                 MessagesPlaceholder(variable_name="messages"),
#                 ("human", "{user_input}"),
#             ]
#         )

#     async def post_message(self, message: str):
#         self.messages.append(("user", message))
#         # Форматируем историю сообщений
#         formatted_history = [
#             {"role": role, "content": content} for role, content in self.messages
#         ]

#         # Создаем цепочку
#         chain = self.prompt_template | self.chat
#         response = await chain.ainvoke({"user_input": message, "messages": formatted_history})

#         # Обновляем историю
#         self.messages.append(("assistant", response.content))

#         # Ограничиваем длину истории
#         if len(self.messages) > 20:
#             self.messages = self.messages[-2:]

#         return response.content
