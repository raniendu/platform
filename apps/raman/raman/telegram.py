from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import telegramify_markdown

from raman.gateway import InboundMessage, MessageEnqueuer, ThreadStore
from raman.logging import chat_hash, get_logger
from raman.settings import RamanSettings
from raman.telegram_config import LEGACY_BOT_NAME, TelegramBotConfig

MAX_TELEGRAM_MESSAGE = 4096
TELEGRAM_PARSE_MODE = "MarkdownV2"
logger = get_logger(__name__)


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
        settings: RamanSettings,
        bot: TelegramBotConfig | None = None,
        store: ThreadStore,
        enqueue_message: MessageEnqueuer | None,
        send_text: SendText | None = None,
    ):
        self.settings = settings
        self.bot = bot or TelegramBotConfig(
            name=LEGACY_BOT_NAME,
            default_agent=settings.default_agent,
            bot_token=settings.telegram_bot_token or "",
            webhook_secret=settings.telegram_webhook_secret or "",
            allowed_chat_ids=settings.telegram_allowed_chat_ids,
            api_base_url=settings.telegram_api_base_url,
            legacy=True,
        )
        self.store = store
        self.enqueue_message = enqueue_message
        self._send_text = send_text

    async def handle_update(self, update: dict[str, Any]) -> TelegramWebhookResult:
        update_id = update.get("update_id")
        log = logger.bind(update_id=update_id)
        log.info("telegram_update_received")
        message = parse_text_message(update)
        if message is None:
            result = await self._handle_non_text_update(update)
            log.info("telegram_update_processed", status=result.status)
            return result
        log = log.bind(
            chat_hash=chat_hash(message.chat_id),
            chat_type=message.chat_type,
            text_length=len(message.text),
            has_from_id=message.from_id is not None,
        )
        if not self.store.claim_telegram_update(self.bot.name, message.update_id):
            log.info("telegram_update_duplicate")
            return TelegramWebhookResult(status="duplicate")
        if message.chat_id not in self.bot.allowed_chat_id_set:
            log.warning("telegram_chat_rejected")
            await self.send_message(message.chat_id, "This bot is private.")
            return TelegramWebhookResult(status="rejected")
        if message.text.startswith("/"):
            result = await self._handle_command(message)
            log.info("telegram_command_processed", status=result.status)
            return result
        if self.enqueue_message is None:
            log.error("telegram_enqueue_missing")
            raise RuntimeError("Telegram enqueue_message callback is not configured")
        enqueued = await self.enqueue_message(
            InboundMessage(
                interface=self.bot.interface,
                external_thread_id=str(message.chat_id),
                prompt=message.text,
                agent_name=None,
                default_agent=self.bot.default_agent,
                metadata={
                    "telegram_bot": self.bot.name,
                    "chat_type": message.chat_type,
                    "from_id": message.from_id,
                    "update_id": message.update_id,
                },
            )
        )
        log.info(
            "telegram_message_enqueued",
            workflow_id=enqueued.workflow_id,
            status=enqueued.status,
        )
        return TelegramWebhookResult(
            status=enqueued.status,
            workflow_id=enqueued.workflow_id,
        )

    async def send_message(self, chat_id: int, text: str) -> None:
        chunks = format_for_telegram(text)
        log = logger.bind(
            chat_hash=chat_hash(chat_id),
            chunk_count=len(chunks),
            output_length=len(text),
        )
        log.info("telegram_send_started")
        if self._send_text is not None:
            for index, chunk in enumerate(chunks, start=1):
                await self._send_text(chat_id, chunk)
                log.info(
                    "telegram_send_chunk_succeeded",
                    chunk_index=index,
                    transport="injected",
                )
            log.info("telegram_send_succeeded")
            return
        if not self.bot.bot_token:
            log.error("telegram_send_unconfigured")
            raise RuntimeError(
                f"Telegram bot token is not configured for {self.bot.name}"
            )
        async with httpx.AsyncClient(base_url=self.bot.api_base_url) as client:
            for index, chunk in enumerate(chunks, start=1):
                try:
                    response = await client.post(
                        f"/bot{self.bot.bot_token}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": chunk,
                            "parse_mode": TELEGRAM_PARSE_MODE,
                        },
                    )
                    response.raise_for_status()
                    log.info(
                        "telegram_send_chunk_succeeded",
                        chunk_index=index,
                        transport="telegram_api",
                        status_code=response.status_code,
                    )
                except httpx.HTTPError:
                    log.exception(
                        "telegram_send_chunk_failed",
                        chunk_index=index,
                        transport="telegram_api",
                    )
                    raise
        log.info("telegram_send_succeeded")

    async def _handle_command(
        self, message: TelegramTextMessage
    ) -> TelegramWebhookResult:
        command, _, arg = message.text.partition(" ")
        command = command.split("@", 1)[0].lower()
        logger.info(
            "telegram_command_received",
            update_id=message.update_id,
            chat_hash=chat_hash(message.chat_id),
            command=command,
        )
        if command in {"/start", "/help"}:
            await self.send_message(
                message.chat_id,
                "Send a text message to chat with the agent. Use /reset to clear history or /agent <name> to switch agents.",
            )
            return TelegramWebhookResult(status="handled")
        if command == "/reset":
            self.store.reset_history(self.bot.interface, str(message.chat_id))
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
            self.store.set_agent(self.bot.interface, str(message.chat_id), agent_name)
            await self.send_message(message.chat_id, f"Agent set to {agent_name}.")
            return TelegramWebhookResult(status="handled")
        await self.send_message(message.chat_id, f"Unknown command: {command}")
        return TelegramWebhookResult(status="handled")

    async def _handle_non_text_update(
        self, update: dict[str, Any]
    ) -> TelegramWebhookResult:
        chat_id = extract_chat_id(update)
        update_id = update.get("update_id")
        log = logger.bind(
            update_id=update_id,
            chat_hash=chat_hash(chat_id) if chat_id is not None else None,
        )
        if chat_id is None or update_id is None:
            log.info("telegram_update_ignored", reason="missing_chat_or_update_id")
            return TelegramWebhookResult(status="ignored")
        if not self.store.claim_telegram_update(self.bot.name, int(update_id)):
            log.info("telegram_update_duplicate")
            return TelegramWebhookResult(status="duplicate")
        if chat_id not in self.bot.allowed_chat_id_set:
            log.warning("telegram_chat_rejected")
            await self.send_message(chat_id, "This bot is private.")
            return TelegramWebhookResult(status="rejected")
        log.info("telegram_non_text_rejected")
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
