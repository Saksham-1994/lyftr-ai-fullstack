from fastapi.testclient import TestClient
from app.main import app
from app import main

def test_health(monkeypatch):
    monkeypatch.setattr(main.settings, "llm_api_keys", ["test-a", "test-b"])
    monkeypatch.setattr(main, "database_is_ready", lambda: True)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["keys_configured"] == 2

def test_chat_and_history(monkeypatch):
    monkeypatch.setattr(main.settings, "llm_api_keys", ["test-a", "test-b"])
    monkeypatch.setattr(main, "generate_reply", lambda messages, simulate_failure=None: (
        "Hello from test", {
            "resolution_source": "LIVE_INFERENCE", "model": "test/model",
            "latency_ms": 10, "input_tokens": 5, "output_tokens": 3,
            "key_id": "key_1", "fallback_attempts": 0
        }
    ))
    with TestClient(app) as client:
        response = client.post("/chat", json={"session_id": "pytest-session", "message": "Hello"})
        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Hello from test"
        assert body["metadata"]["input_tokens"] == 5
        history = client.get("/sessions/pytest-session/messages")
        assert history.status_code == 200
        assert len(history.json()["messages"]) == 2

def test_validation():
    with TestClient(app) as client:
        response = client.post("/chat", json={"session_id": "", "message": "Hi"})
    assert response.status_code == 422
