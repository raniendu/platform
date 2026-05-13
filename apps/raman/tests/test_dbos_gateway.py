from inspect import unwrap

import pytest

from raman.dbos_gateway import (
    TELEGRAM_FAILURE_REPLY,
    _send_processing_failure_reply,
    process_inbound_message_event,
)
from raman.gateway import (
    InboundMessage,
    cloud_event_to_dict,
    make_message_received_event,
)


@pytest.mark.asyncio
async def test_processing_failure_reply_is_sent_for_telegram(monkeypatch):
    sent = []

    async def fake_send_telegram_reply(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(
        "raman.dbos_gateway.send_telegram_reply", fake_send_telegram_reply
    )

    delivered = await _send_processing_failure_reply(
        InboundMessage(
            interface="telegram",
            external_thread_id="123",
            prompt="do not echo",
            agent_name=None,
            metadata={"update_id": 42},
        )
    )

    assert delivered is True
    assert sent == [(123, TELEGRAM_FAILURE_REPLY)]
    assert "do not echo" not in TELEGRAM_FAILURE_REPLY


@pytest.mark.asyncio
async def test_processing_failure_reply_is_skipped_for_non_telegram(monkeypatch):
    sent = []

    async def fake_send_telegram_reply(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(
        "raman.dbos_gateway.send_telegram_reply", fake_send_telegram_reply
    )

    delivered = await _send_processing_failure_reply(
        InboundMessage(
            interface="manual",
            external_thread_id="123",
            prompt="hello",
            agent_name=None,
            metadata={},
        )
    )

    assert delivered is False
    assert sent == []


@pytest.mark.asyncio
async def test_processing_failure_reply_send_errors_do_not_escape(monkeypatch):
    async def fake_send_telegram_reply(chat_id, text):
        raise RuntimeError("telegram send failed")

    monkeypatch.setattr(
        "raman.dbos_gateway.send_telegram_reply", fake_send_telegram_reply
    )

    delivered = await _send_processing_failure_reply(
        InboundMessage(
            interface="telegram",
            external_thread_id="123",
            prompt="hello",
            agent_name=None,
            metadata={},
        )
    )

    assert delivered is False


@pytest.mark.asyncio
async def test_inbound_workflow_sends_failure_reply_before_reraising(monkeypatch):
    sent = []

    class FailingConversationService:
        def __init__(self, *, settings, store):
            pass

        async def send_message(self, message):
            raise RuntimeError("agent failed")

    async def fake_send_telegram_reply(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr("raman.gateway.ConversationService", FailingConversationService)
    monkeypatch.setattr(
        "raman.dbos_gateway.send_telegram_reply", fake_send_telegram_reply
    )
    message = InboundMessage(
        interface="telegram",
        external_thread_id="123",
        prompt="do not echo",
        agent_name=None,
        metadata={"update_id": 42},
    )

    with pytest.raises(RuntimeError, match="agent failed"):
        await unwrap(process_inbound_message_event)(
            cloud_event_to_dict(make_message_received_event(message))
        )

    assert sent == [(123, TELEGRAM_FAILURE_REPLY)]
