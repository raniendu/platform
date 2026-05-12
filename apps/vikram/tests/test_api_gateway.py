from fastapi.testclient import TestClient

from vikram import api
from vikram.gateway import EnqueuedEvent
from vikram.settings import VikramSettings


class FakeDispatcher:
    def __init__(self):
        self.messages = []

    async def enqueue_message(self, message):
        self.messages.append(message)
        return EnqueuedEvent(workflow_id="wf-1", status="queued")

    async def get_event_status(self, workflow_id):
        return {
            "workflow_id": workflow_id,
            "status": "SUCCESS",
            "result": {"output": "hello"},
            "error": None,
        }


def test_thread_message_endpoint_enqueues_message(monkeypatch):
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(api, "_get_dispatcher", lambda: dispatcher)

    with TestClient(api.app) as client:
        response = client.post(
            "/threads/web/abc/messages",
            json={"prompt": "hello", "agent": "vikram"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "workflow_id": "wf-1",
        "thread_id": "web:abc",
        "status": "queued",
    }
    assert dispatcher.messages[0].interface == "web"
    assert dispatcher.messages[0].external_thread_id == "abc"


def test_event_status_endpoint_returns_dispatcher_status(monkeypatch):
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(api, "_get_dispatcher", lambda: dispatcher)

    with TestClient(api.app) as client:
        response = client.get("/events/wf-1")

    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert response.json()["result"] == {"output": "hello"}


def test_telegram_webhook_rejects_bad_secret(monkeypatch):
    monkeypatch.setattr(
        api,
        "_settings",
        VikramSettings(
            _env_file=None,
            telegram_bot_token="token",
            telegram_webhook_secret="secret",
            telegram_allowed_chat_ids="123",
        ),
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            json={},
        )

    assert response.status_code == 403
