import pytest

from vikram.gateway import EnqueuedEvent, ThreadStore
from vikram.settings import VikramSettings
from vikram.telegram import TelegramAdapter, format_for_telegram


def expected(text: str) -> list[str]:
    return format_for_telegram(text)


def test_format_for_telegram_converts_markdown_to_markdownv2():
    chunks = format_for_telegram(
        "**Bold heading**\n\n*   bullet one\n*   bullet two\n\n`code`"
    )
    assert len(chunks) == 1
    body = chunks[0]
    assert "*Bold heading*" in body
    assert "**" not in body
    assert "⦁ bullet one" in body
    assert "⦁ bullet two" in body
    assert "`code`" in body


def test_format_for_telegram_empty_input():
    assert format_for_telegram("") == [""]


def make_settings(**overrides):
    values = {
        "telegram_bot_token": "token",
        "telegram_webhook_secret": "secret",
        "telegram_allowed_chat_ids": "123",
    }
    values.update(overrides)
    return VikramSettings(_env_file=None, **values)


def text_update(text, *, chat_id=123, update_id=1, chat_type="private"):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 10,
            "text": text,
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"id": 999},
        },
    }


@pytest.mark.asyncio
async def test_telegram_enqueues_allowed_text_message(tmp_path):
    enqueued = []
    sent = []

    async def enqueue(message):
        enqueued.append(message)
        return EnqueuedEvent(workflow_id="wf-1", status="queued")

    async def send_text(chat_id, text):
        sent.append((chat_id, text))

    adapter = TelegramAdapter(
        settings=make_settings(),
        store=ThreadStore(tmp_path / "vikram.sqlite3"),
        enqueue_message=enqueue,
        send_text=send_text,
    )

    result = await adapter.handle_update(text_update("hello"))

    assert result.status == "queued"
    assert result.workflow_id == "wf-1"
    assert enqueued[0].interface == "telegram"
    assert enqueued[0].external_thread_id == "123"
    assert enqueued[0].prompt == "hello"
    assert sent == []


@pytest.mark.asyncio
async def test_telegram_rejects_unknown_chat(tmp_path):
    sent = []

    async def send_text(chat_id, text):
        sent.append((chat_id, text))

    adapter = TelegramAdapter(
        settings=make_settings(),
        store=ThreadStore(tmp_path / "vikram.sqlite3"),
        enqueue_message=None,
        send_text=send_text,
    )

    result = await adapter.handle_update(text_update("hello", chat_id=999))

    assert result.status == "rejected"
    assert sent == [(999, chunk) for chunk in expected("This bot is private.")]


@pytest.mark.asyncio
async def test_telegram_rejects_allowed_non_text_message(tmp_path):
    sent = []

    async def send_text(chat_id, text):
        sent.append((chat_id, text))

    adapter = TelegramAdapter(
        settings=make_settings(),
        store=ThreadStore(tmp_path / "vikram.sqlite3"),
        enqueue_message=None,
        send_text=send_text,
    )

    result = await adapter.handle_update(
        {
            "update_id": 2,
            "message": {
                "message_id": 11,
                "chat": {"id": 123, "type": "private"},
                "photo": [{"file_id": "abc"}],
            },
        }
    )

    assert result.status == "rejected"
    assert sent == [(123, chunk) for chunk in expected("Text messages only for now.")]


@pytest.mark.asyncio
async def test_telegram_reset_command_clears_history(tmp_path):
    store = ThreadStore(tmp_path / "vikram.sqlite3")
    store.set_history("telegram", "123", agent_name="vikram", message_history_json=b"[]")
    sent = []

    async def send_text(chat_id, text):
        sent.append((chat_id, text))

    adapter = TelegramAdapter(
        settings=make_settings(),
        store=store,
        enqueue_message=None,
        send_text=send_text,
    )

    result = await adapter.handle_update(text_update("/reset"))

    assert result.status == "handled"
    assert (
        store.get_thread("telegram", "123", default_agent="vikram").message_history_json
        is None
    )
    assert sent == [(123, chunk) for chunk in expected("Conversation reset.")]


@pytest.mark.asyncio
async def test_telegram_agent_command_persists_existing_spec(tmp_path):
    store = ThreadStore(tmp_path / "vikram.sqlite3")
    sent = []

    async def send_text(chat_id, text):
        sent.append((chat_id, text))

    adapter = TelegramAdapter(
        settings=make_settings(),
        store=store,
        enqueue_message=None,
        send_text=send_text,
    )

    result = await adapter.handle_update(text_update("/agent vikram"))

    assert result.status == "handled"
    assert (
        store.get_thread("telegram", "123", default_agent="alfred").agent_name
        == "vikram"
    )
    assert sent == [(123, chunk) for chunk in expected("Agent set to vikram.")]
