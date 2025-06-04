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


## Endpoints

### 1. **Register Company**  
- **POST** `/company/register`

  Registers a new company and returns an API key.
  
  **Request Model**: `RegisterRequest`
    
  **Response Model**: `RegisterResponse`
    
  **Body**:
  ```json
  { "name": "Company Name" }
  ```

### 2. **Deleting Company**  
- **DELETE** `/company/delete`

  Delete a company with all data of company asynchronously.
      
  **Response Model**: `TaskResponse`
  
### 3. Upload Documents  
- **POST**  `/documents/upload`

  Uploads documents asynchronously. 
  
  **Request Model** : `UploadRequest`
  
  **Response Model** : `TaskResponse`
  
  **Body** :
  ```json
  { "documents": ["file_path1", "file_path2"] }
  ```

### 4. Delete Documents   
- **DELETE**  `/documents/delete/all`

  Deletes all documents for a company (async).
  
  **Response Model** : `TaskResponse`
  
- **DELETE**  `/documents/delete/{document_id}`
  
  Deletes a specific document by ID.
  
  **Response Model** : `UploadResponse`


### 5. Task Status  
- **GET**  `/documents/upload/status/{task_id}`
- **GET**  `/documents/delete/status/{task_id}`
- **GET**  `/company/delete/status/{task_id}`

  Check status/results of async tasks.
  
  **Response Model** : `TaskStatusResponse`

### 6. Chat Interface 
- **POST**  `/chat`

  Process chat queries with context from vector search and Redis history.
  
  **Request Model** : `ChatRequest`
  
  **Response Model** : `ChatResponse`
  
  **Features** :
  - Uses Azure OpenAI (fallback to DeepSeek if unavailable).
  - Stores history in Redis for session context.

### 7. Admin Prompt   
- **POST**  `/prompt`

  Save a custom system prompt for a company.
  
  **Request Model** : `AdminPromptRequest`
  
  **Body** :
  ```json
  { "prompt": "Custom instructions..." }
  ```

## Dependencies
- Azure AI Search : Vector/document search.
- Redis : Session history persistence and broker for celery.
- Celery : Async task management.
- OpenAI/DeepSeek : LLM fallback logic.
All of them you may find at ```pyproject.toml``` in key ```dependencies```.

## Setup
1. Configure .env with Azure/DeepSeek credentials. For simpler use there is an .env.example.
2. Start Redis and Celery worker.
3. Run ASGI.
