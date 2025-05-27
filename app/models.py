from uuid import uuid4
from typing import Optional
from sqlmodel import SQLModel, Field


class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    api_key: str = Field(index=True, unique=True, default=str(uuid4()))
