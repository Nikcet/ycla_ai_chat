# ycla_ai_chat

First you should setup the .env variables.

## Run testing environment:
That project uses a uv PM, so you should install uv first:
```bash  
pip install uv
```
Install fixed python version:
```bash
uv python install
```
Install all dependencies:
```bash
uv sync
```
Make init migrations:
```bash
alembic upgrade head
```

Run FastAPI ASGI for development:
```bash
uv run uvicorn main:app --reload
```
### Run redis for development 
```bash
redis-server
```
### Run celery on windows
```bash
celery -A app.celery_worker.celery_tasks worker --loglevel=info --pool=eventlet
```
When you run asgi, you may find docs for that endpoint: "http://localhost:8000/docs"
