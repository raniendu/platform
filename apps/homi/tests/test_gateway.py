from pathlib import Path

import pytest

from homi.gateway import (
    ConversationService,
    InboundMessage,
    ThreadStore,
    make_message_received_event,
)
from homi.settings import HomiSettings


def test_thread_store_persists_thread_agent_and_history(tmp_path):
    store = ThreadStore(tmp_path / "homi.sqlite3")

    thread = store.get_thread("telegram", "123", default_agent="homi")
    assert thread.agent_name == "homi"
    assert thread.message_history_json is None

    store.set_history(
        "telegram", "123", agent_name="alfred", message_history_json=b"[]"
    )
    updated = store.get_thread("telegram", "123", default_agent="homi")

    assert updated.agent_name == "alfred"
    assert updated.message_history_json == b"[]"

    store.reset_history("telegram", "123")
    reset = store.get_thread("telegram", "123", default_agent="homi")

    assert reset.agent_name == "alfred"
    assert reset.message_history_json is None


def test_thread_store_claims_telegram_updates_once(tmp_path):
    store = ThreadStore(tmp_path / "homi.sqlite3")

    assert store.claim_telegram_update(42) is True
    assert store.claim_telegram_update(42) is False


def test_message_received_event_uses_cloudevent_metadata():
    event = make_message_received_event(
        InboundMessage(
            interface="telegram",
            external_thread_id="123",
            prompt="hello",
            agent_name="homi",
            metadata={"chat_type": "private"},
        )
    )

    assert event["type"] == "homi.message.received"
    assert event["source"] == "/interfaces/telegram/threads/123"
    assert event.get_data()["prompt"] == "hello"
    assert event.get_data()["agent_name"] == "homi"


@pytest.mark.asyncio
async def test_conversation_service_runs_agent_with_persisted_history(tmp_path):
    store = ThreadStore(tmp_path / "homi.sqlite3")
    calls = []

    class FakeResult:
        output = "reply"
        message_history_json = b"[]"

    class FakeAgent:
        async def run(self, prompt, *, message_history_json, conversation_id):
            calls.append((prompt, message_history_json, conversation_id))
            return FakeResult()

    service = ConversationService(
        settings=HomiSettings(_env_file=None),
        store=store,
        agent_factory=lambda name: FakeAgent(),
    )

    reply = await service.send_message(
        InboundMessage(
            interface="telegram",
            external_thread_id="123",
            prompt="hello",
            agent_name=None,
            metadata={},
        )
    )

    assert reply.output == "reply"
    assert reply.agent_name == "homi"
    assert calls == [("hello", None, "telegram:123")]
    assert (
        store.get_thread("telegram", "123", default_agent="homi").message_history_json
        == b"[]"
    )
