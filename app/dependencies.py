import os
from uuid import uuid4
from openai.lib.azure import AzureOpenAI
from dotenv import load_dotenv
from loguru import logger
from app.config import system_prompt, assistant_prompt, user_prompt

if not load_dotenv():
    logger.error("Install dotenv and create a '.env' file.")
    raise ConnectionError("Install dotenv and/or create a '.env' file.")
    
try:
    SECRET_KEY = os.getenv("OPENAI_API_KEY")
    ENDPOINT = os.getenv("OPENAI_API_URL")
    DEPLOYMENT = os.getenv("DEPLOYMENT_NAME")
    API_VERSION = os.getenv("API_VERSION")
except Exception as e:
    logger.error(f"Check the env variables. {e}")
    raise

class Company:
    def __init__(self, name, integration=None):
        self.name = name
        self.integration = integration
        self.active_chats: dict[str, "Chat"] = {}

class Admin:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.company = None

class Chat(Company):
    def __init__(self):
        super().__init__(self)
        self.chat_id = str(uuid4())
        self.client = AzureOpenAI(
            azure_endpoint=ENDPOINT,
            api_key=SECRET_KEY,
            api_version=API_VERSION,
        )
        self.conversation = []

    async def configure_system_prompt(self, message: str) -> None:
        system_prompt["content"] = message
        self.conversation = [system_prompt]
        logger.info("Системный промпт изменен")

    async def add_message(self, message: str) -> str:
        user_prompt["content"] = message
        self.conversation.append(user_prompt)
        response = await self.client.chat.completions.create(
            model=DEPLOYMENT,
            messages=self.conversation,
            max_tokens=10000,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0.6,
            presence_penalty=0.3,
            stop=None,
            stream=False,
        )

        ai_response = response.choices[0].message.content

        assistant_prompt["content"] = ai_response
        self.conversation.append(assistant_prompt)

        return ai_response
