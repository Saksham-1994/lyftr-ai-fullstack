from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .config import settings
from .database import add_message, database_is_ready, get_messages, initialize_database, session_exists
from .llm import CACHE_ENABLED, generate_reply

app = FastAPI(title="Lyftr AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Simulate-Failure"],
)

@app.on_event("startup")
def startup():
    initialize_database()

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: str | None = None

    @field_validator("session_id", "message")
    @classmethod
    def trim_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Field must not be empty")
        return value

@app.get("/health")
def health():
    if not database_is_ready():
        raise HTTPException(status_code=503, detail="database unavailable")
    if not settings.llm_api_keys:
        raise HTTPException(status_code=503, detail="LLM key pool not configured")
    return {"status": "ok", "keys_configured": len(settings.llm_api_keys), "cache_enabled": CACHE_ENABLED}

@app.post("/chat")
def chat(request: ChatRequest, x_simulate_failure: str | None = Header(default=None)):
    history = get_messages(request.session_id)
    prompt = request.system_prompt.strip() if request.system_prompt and request.system_prompt.strip() else settings.default_system_prompt
    llm_messages = [{"role": "system", "content": prompt}]
    llm_messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    llm_messages.append({"role": "user", "content": request.message})
    try:
        reply, metadata = generate_reply(llm_messages, x_simulate_failure)
    except RuntimeError as exc:
        if str(exc) == "all providers unavailable":
            raise HTTPException(status_code=503, detail="all providers unavailable")
        raise HTTPException(status_code=503, detail="AI provider unavailable")
    except Exception:
        raise HTTPException(status_code=503, detail="AI provider unavailable")

    # Persist only after successful inference/cache resolution.
    add_message(request.session_id, "user", request.message)
    add_message(request.session_id, "assistant", reply, metadata)
    return {"session_id": request.session_id, "reply": reply, "metadata": metadata}

@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_id": session_id, "messages": get_messages(session_id)}
