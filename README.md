# bookcase-management

`bookcase-management` is a full-stack project with a Flask backend and a React frontend.

## Structure

- `backend/`: Flask API, SQLite data, reading analysis queue, LLM integration, backend scripts
- `frontend/`: React admin console for model usage and book data management

## Backend

Setup:

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
python app.py
```

Backend default address:

```bash
http://127.0.0.1:8001
```

Important backend env:

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TIMEOUT`
- `LLM_CONNECT_TIMEOUT`
- `LLM_MAX_RETRIES`
- `ANALYSIS_WORKER_CONCURRENCY`
- `CORS_ALLOW_ORIGINS`

## Frontend

Setup:

```bash
cd frontend
cp .env.example .env
npm install
npm run build
```

Frontend env:

- `VITE_API_BASE_URL`: backend API base URL, default `http://127.0.0.1:8001`

After build, open:

```bash
http://127.0.0.1:8001/admin
```

## Current Features

- ISBN-based book lookup with SQLite cache
- Reading preference analysis task queue
- Same-book-list hash cache for analysis results
- Model usage statistics by provider, by model, and global totals
- Admin book list with search and pagination

## Reading Preference Task APIs

Create task:

```bash
curl -X POST http://127.0.0.1:8001/agent/reading-preferences/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "book_titles": ["八次危机", "史蒂夫·乔布斯", "全球通史", "机器学习", "刑法学讲义", "大设计"]
  }'
```

Poll task:

```bash
curl http://127.0.0.1:8001/agent/reading-preferences/tasks/<task_id>
```

## Admin APIs

- `GET /admin/api/usage`
- `GET /admin/api/books`
