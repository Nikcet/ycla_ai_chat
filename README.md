# ycla_ai_chat


Запустить тестовое окружение:
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
Запустить redis
```bash
redis-server
```
Запустить celery
```bash
celery -A app.celery_worker.celery_tasks worker --loglevel=info --pool=eventlet
```


