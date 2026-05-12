from fastapi.testclient import TestClient

from homi.api import app


def test_healthz_returns_ok():
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_unknown_agent_returns_404():
    with TestClient(app) as client:
        response = client.post("/chat", json={"prompt": "hi", "agent": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Unknown agent")


def test_chat_rejects_empty_prompt():
    with TestClient(app) as client:
        response = client.post("/chat", json={"prompt": "", "agent": "homi"})

    assert response.status_code == 422
