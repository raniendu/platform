from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import telegramify_markdown

from homi.gateway import InboundMessage, MessageEnqueuer, ThreadStore
from homi.settings import HomiSettings

MAX_TELEGRAM_MESSAGE = 4096
TELEGRAM_PARSE_MODE = "MarkdownV2"


@dataclass(frozen=True)
class TelegramWebhookResult:
    status: str
    workflow_id: str | None = None


@dataclass(frozen=True)
class TelegramTextMessage:
    update_id: int
    chat_id: int
    chat_type: str
    text: str
    from_id: int | None


SendText = Callable[[int, str], Awaitable[None]]


class TelegramAdapter:
    def __init__(
        self,
        *,
        settings: HomiSettings,
        store: ThreadStore,
        enqueue_message: MessageEnqueuer | None,
        send_text: SendText | None = None,
    ):
        self.settings = settings
        self.store = store
        self.enqueue_message = enqueue_message
        self._send_text = send_text

    async def handle_update(self, update: dict[str, Any]) -> TelegramWebhookResult:
        message = parse_text_message(update)
        if message is None:
            return await self._handle_non_text_update(update)
        if not self.store.claim_telegram_update(message.update_id):
            return TelegramWebhookResult(status="duplicate")
        if message.chat_id not in self.settings.telegram_allowed_chat_id_set:
            await self.send_message(message.chat_id, "This bot is private.")
            return TelegramWebhookResult(status="rejected")
        if message.text.startswith("/"):
            return await self._handle_command(message)
        if self.enqueue_message is None:
            raise RuntimeError("Telegram enqueue_message callback is not configured")
        enqueued = await self.enqueue_message(
            InboundMessage(
                interface="telegram",
                external_thread_id=str(message.chat_id),
                prompt=message.text,
                agent_name=None,
                metadata={
                    "chat_type": message.chat_type,
                    "from_id": message.from_id,
                    "update_id": message.update_id,
                },
            )
        )
        return TelegramWebhookResult(
            status=enqueued.status,
            workflow_id=enqueued.workflow_id,
        )

    async def send_message(self, chat_id: int, text: str) -> None:
        chunks = format_for_telegram(text)
        if self._send_text is not None:
            for chunk in chunks:
                await self._send_text(chat_id, chunk)
            return
        if not self.settings.telegram_bot_token:
            raise RuntimeError("HOMI_TELEGRAM_BOT_TOKEN is not configured")
        async with httpx.AsyncClient(
            base_url=self.settings.telegram_api_base_url
        ) as client:
            for chunk in chunks:
                response = await client.post(
                    f"/bot{self.settings.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": TELEGRAM_PARSE_MODE,
                    },
                )
                response.raise_for_status()

    async def _handle_command(
        self, message: TelegramTextMessage
    ) -> TelegramWebhookResult:
        command, _, arg = message.text.partition(" ")
        command = command.split("@", 1)[0].lower()
        if command in {"/start", "/help"}:
            await self.send_message(
                message.chat_id,
                "Send a text message to chat with the agent. Use /reset to clear history or /agent <name> to switch agents.",
            )
            return TelegramWebhookResult(status="handled")
        if command == "/reset":
            self.store.reset_history("telegram", str(message.chat_id))
            await self.send_message(message.chat_id, "Conversation reset.")
            return TelegramWebhookResult(status="handled")
        if command == "/agent":
            agent_name = arg.strip()
            if not agent_name:
                await self.send_message(message.chat_id, "Usage: /agent <name>")
                return TelegramWebhookResult(status="handled")
            spec_path = self.settings.spec_root / agent_name / "agent.toml"
            if not spec_path.exists():
                await self.send_message(message.chat_id, f"Unknown agent: {agent_name}")
                return TelegramWebhookResult(status="handled")
            self.store.set_agent("telegram", str(message.chat_id), agent_name)
            await self.send_message(message.chat_id, f"Agent set to {agent_name}.")
            return TelegramWebhookResult(status="handled")
        await self.send_message(message.chat_id, f"Unknown command: {command}")
        return TelegramWebhookResult(status="handled")

    async def _handle_non_text_update(
        self, update: dict[str, Any]
    ) -> TelegramWebhookResult:
        chat_id = extract_chat_id(update)
        update_id = update.get("update_id")
        if chat_id is None or update_id is None:
            return TelegramWebhookResult(status="ignored")
        if not self.store.claim_telegram_update(int(update_id)):
            return TelegramWebhookResult(status="duplicate")
        if chat_id not in self.settings.telegram_allowed_chat_id_set:
            await self.send_message(chat_id, "This bot is private.")
            return TelegramWebhookResult(status="rejected")
        await self.send_message(chat_id, "Text messages only for now.")
        return TelegramWebhookResult(status="rejected")


def parse_text_message(update: dict[str, Any]) -> TelegramTextMessage | None:
    raw_message = update.get("message")
    if not isinstance(raw_message, dict):
        return None
    text = raw_message.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    chat = raw_message.get("chat")
    if not isinstance(chat, dict) or "id" not in chat:
        return None
    raw_from = raw_message.get("from")
    from_id = raw_from.get("id") if isinstance(raw_from, dict) else None
    return TelegramTextMessage(
        update_id=int(update["update_id"]),
        chat_id=int(chat["id"]),
        chat_type=str(chat.get("type", "unknown")),
        text=text.strip(),
        from_id=int(from_id) if from_id is not None else None,
    )


def extract_chat_id(update: dict[str, Any]) -> int | None:
    raw_message = update.get("message")
    if not isinstance(raw_message, dict):
        return None
    chat = raw_message.get("chat")
    if not isinstance(chat, dict) or "id" not in chat:
        return None
    return int(chat["id"])


def format_for_telegram(text: str) -> list[str]:
    if not text:
        return [""]
    plain, entities = telegramify_markdown.convert(text)
    return [
        telegramify_markdown.entities_to_markdownv2(chunk_text, chunk_entities)
        for chunk_text, chunk_entities in telegramify_markdown.split_entities(
            plain, entities, max_utf16_len=MAX_TELEGRAM_MESSAGE
        )
    ]
