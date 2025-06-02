# ycla_ai_chat

First you should setup the .env variables.

## Run testing environment:
```bash  
pip install uv
```
```bash
uv python install
```
```bash
uv sync
```
```bash
uv run uvicorn main:app --reload
```
### Run redis 
```bash
redis-server
```
### Run celery on windows
```bash
celery -A app.celery_worker.celery_tasks worker --loglevel=info --pool=eventlet
```


