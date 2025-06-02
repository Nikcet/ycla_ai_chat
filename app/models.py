from uuid import uuid4
from shortuuid import uuid
from sqlmodel import SQLModel, Field
from typing import Optional


class Company(SQLModel, table=True):
    """
    Represents a company in the database.

    Attributes:
        id (str): The unique identifier for the company.
        name (str): The name of the company.
        api_key (str): The API key for the company.
    """

    id: str = Field(default_factory=uuid, primary_key=True)
    name: str = Field(index=True)
    api_key: str = Field(default_factory=lambda: str(uuid4()), index=True, unique=True)


class FileMetadata(SQLModel, table=True):
    """
    Represents file metadata in the database.

    Attributes:
        id (str): The unique identifier for the file metadata.
        file_name (str): The name of the file.
        company_id (str): The ID of the company associated with the file.
        document_id (str): The ID of the document associated with the file.
    """

    id: str = Field(default_factory=uuid, primary_key=True)
    file_name: str
    company_id: str = Field(foreign_key="company.id")
    document_id: str


class AdminPrompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt: str
    company_id: str = Field(foreign_key="company.id")