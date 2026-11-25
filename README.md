# Lyftr AI — LLM Chatbot with Key Failover & Response Caching

A full-stack AI chatbot built for the Lyftr AI assignment using React, FastAPI, LiteLLM, SQLite and Docker.

## 1. Live URLs

- Frontend: Add your deployed frontend URL after deployment.
- Backend: Add your deployed backend URL after deployment.
- Health: `<backend-url>/health`
- API docs: `<backend-url>/docs`

## 2. Run locally: with Docker and without

### Requirements
- Docker Desktop and Docker Compose (recommended), or Python 3.12+ and Node.js 20+
- Two API keys from the provider configured by `LLM_MODEL`

### Docker (required workflow)
1. Copy `.env.example` to `.env`.
2. Put two valid provider keys in `LLM_API_KEYS`. Do not share or commit `.env`.
3. Confirm `LLM_MODEL` matches the provider for those keys. The default is `gemini/gemini-2.0-flash`.
4. Run:

```bash
make up
```

5. Open the frontend at http://localhost:3000 and API at http://localhost:8000/docs.
6. Stop with:

```bash
make down
```

SQLite and LiteLLM cache data persist in the named `lyftr_data` Docker volume mounted at `/data`.

### Without Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export LLM_API_KEYS="key_one,key_two"
export LLM_MODEL="gemini/gemini-2.0-flash"
export DATABASE_URL="sqlite:///./app.db"
export ALLOWED_ORIGINS="http://localhost:3000"
export ENABLE_FAILURE_SIMULATION="true"
uvicorn app.main:app --reload --port 8000
```

Frontend in another terminal:

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev -- --port 3000
```

## 3. Design decisions: key fallback, caching, SQLite session storage

- **Key fallback:** keys are read from `LLM_API_KEYS` in order and assigned safe identifiers `key_1`, `key_2`, etc. Provider errors are caught and the next key is attempted. Raw API keys are never returned to the browser.
- **Caching:** LiteLLM's disk cache is enabled. An exact request fingerprint (model plus the complete system/history/new-message list) is used to return identical cached replies across sessions. Cache metadata uses `LLM_CACHE`, null `key_id`, and zero fallback attempts.
- **SQLite:** all user and assistant messages are stored in SQLite. The database is created on startup and lives under `/data` in Docker. History is scoped by `session_id`.
- **Token usage:** metadata is attached to each assistant response and represents that request's prompt and completion token counts, not a conversation total.
- **Security:** keys are environment variables, CORS is configurable, and provider exceptions are not exposed to clients.

## 4. Verification: how to see failover, cache hits and per-message token usage

### Health
```bash
curl http://localhost:8000/health
```

### Send a message
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-a","message":"What is the capital of France?"}'
```

### Cache hit
Repeat the same first message with a new session ID. The full LLM message list is identical, so the second request should return `LLM_CACHE`, the same reply and `key_id: null`.

### Failover
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id":"failover-a","message":"Explain failover in one sentence."}'
```
Expected: HTTP 200, `key_id` is `key_2`, and `fallback_attempts` is 1.

### All providers unavailable
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id":"failover-b","message":"This request should fail safely."}'
```
Expected: HTTP 503 with `{"detail":"all providers unavailable"}`. Failed requests are not stored.

### Session history
```bash
curl http://localhost:8000/sessions/demo-a/messages
```

### Automated tests
```bash
cd backend
pip install -r requirements.txt
pytest -q
```

## 5. Setup Used: your editor and AI tools

Fill in the actual tools used before submitting (for example: VS Code, ChatGPT, GitHub Copilot).

## 6. Bonus features (if any): what you added beyond the requirements and why

- Custom system prompt control for each chat session.
- Responsive dark interface with copy-response action and API connectivity indicator.
- Docker named volume for both SQLite history and LiteLLM disk cache.
- API documentation via FastAPI Swagger UI.

## API contract

- `GET /health`
- `POST /chat`
- `GET /sessions/{session_id}/messages`

The chat response metadata contains `resolution_source`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, `key_id`, and `fallback_attempts`.

## Important implementation notes

The in-process exact-response index is used alongside LiteLLM's built-in disk cache to preserve the assignment's exact cache semantics across sessions in a running backend process. For multi-replica production deployment, replace the in-process index with a shared persistent cache strategy while retaining the required LiteLLM cache. For the assignment's single backend instance, keep one backend replica so cache behavior remains consistent.

Do not submit until you have tested using real provider keys and replaced the Live URLs above with the public deployed URLs.
