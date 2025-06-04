import asyncio
import os
import sys

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Make sure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

from sqlmodel import SQLModel
from app import settings

target_metadata = SQLModel.metadata


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=False,  # Adjust as needed
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    url = settings.pg_url
    connectable = create_async_engine(url)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


asyncio.run(run_migrations_online())
