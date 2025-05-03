from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.endpoints import router
from app import logger

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.success("Server is starting up.")
    yield
    logger.warning("Server is shutting down.")


@app.get("/")
async def root():
    return {"message": "Ok"}


app.router.lifespan_context = lifespan
app.include_router(router)
