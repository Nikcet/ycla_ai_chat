from uuid import uuid4
from shortuuid import uuid
from sqlmodel import SQLModel, Field


class Company(SQLModel, table=True):
    id: str = Field(default_factory=uuid, primary_key=True)
    name: str = Field(index=True)
    api_key: str = Field(default_factory=lambda: str(uuid4()), index=True, unique=True)


class FileMetadata(SQLModel, table=True):
    id: str = Field(default_factory=uuid, primary_key=True)
    file_name: str
    company_id: str = Field(foreign_key="company.id")
    document_id: str
