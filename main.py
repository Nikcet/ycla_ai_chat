from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.endpoints import router
from app import logger
from sqlmodel import SQLModel
from app.clients import engine

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ycla.ai/"],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS", "DELETE"],
    allow_headers=["*"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    logger.success("Server is starting up.")
    yield
    logger.warning("Server is shutting down.")


app.router.lifespan_context = lifespan
app.include_router(router)
