from __future__ import annotations

from pathlib import Path
from typing import Any

from dbos import DBOS, Queue

from vikram.gateway import (
    EnqueuedEvent,
    InboundMessage,
    ThreadStore,
    cloud_event_from_dict,
    cloud_event_to_dict,
    inbound_message_from_event,
    make_message_received_event,
    make_reply_requested_event,
)
from vikram.settings import VikramSettings
from vikram.telegram import TelegramAdapter

INBOUND_QUEUE = Queue("vikram-inbound", concurrency=1, polling_interval_sec=0.1)
OUTBOUND_QUEUE = Queue("vikram-outbound", concurrency=1, polling_interval_sec=0.1)

_configured = False


class EventDispatcher:
    async def enqueue_message(self, message: InboundMessage) -> EnqueuedEvent:
        event = make_message_received_event(message)
        handle = await INBOUND_QUEUE.enqueue_async(
            process_inbound_message_event,
            cloud_event_to_dict(event),
        )
        return EnqueuedEvent(workflow_id=handle.workflow_id, status="queued")

    async def get_event_status(self, workflow_id: str) -> dict[str, Any]:
        status = await DBOS.get_workflow_status_async(workflow_id)
        if status is None:
            return {
                "workflow_id": workflow_id,
                "status": "NOT_FOUND",
                "result": None,
                "error": None,
            }
        return {
            "workflow_id": status.workflow_id,
            "status": status.status,
            "result": status.output,
            "error": str(status.error) if status.error else None,
        }


def configure_dbos(settings: VikramSettings) -> None:
    global _configured
    if _configured:
        return
    _ensure_sqlite_parent(settings.effective_dbos_system_database_url)
    DBOS(
        config={
            "name": "vikram",
            "system_database_url": settings.effective_dbos_system_database_url,
            "run_admin_server": False,
        }
    )
    _configured = True


def launch_dbos(settings: VikramSettings) -> None:
    configure_dbos(settings)
    DBOS.launch()


def shutdown_dbos() -> None:
    global _configured
    DBOS.destroy()
    _configured = False


@DBOS.workflow(name="vikram_process_inbound_message")
async def process_inbound_message_event(event_dict: dict[str, Any]) -> dict[str, Any]:
    from vikram.gateway import ConversationService

    event = cloud_event_from_dict(event_dict)
    message = inbound_message_from_event(event)
    settings = VikramSettings()
    store = ThreadStore(settings.vikram_db_path)
    reply = await ConversationService(settings=settings, store=store).send_message(
        message
    )
    reply_event = make_reply_requested_event(message, reply)
    if reply.interface == "telegram":
        await OUTBOUND_QUEUE.enqueue_async(
            deliver_reply_event,
            cloud_event_to_dict(reply_event),
        )
    return {
        "agent": reply.agent_name,
        "output": reply.output,
        "thread_id": f"{reply.interface}:{reply.external_thread_id}",
    }


@DBOS.workflow(name="vikram_deliver_reply")
async def deliver_reply_event(event_dict: dict[str, Any]) -> dict[str, Any]:
    event = cloud_event_from_dict(event_dict)
    data = event.get_data()
    if not isinstance(data, dict):
        raise ValueError("Reply event data must be an object")
    if data["interface"] != "telegram":
        return {"delivered": False, "reason": "unsupported interface"}
    await send_telegram_reply(int(data["external_thread_id"]), str(data["output"]))
    return {"delivered": True}


@DBOS.step(name="vikram_send_telegram_reply", retries_allowed=True, max_attempts=3)
async def send_telegram_reply(chat_id: int, text: str) -> None:
    settings = VikramSettings()
    adapter = TelegramAdapter(
        settings=settings,
        store=ThreadStore(settings.vikram_db_path),
        enqueue_message=None,
    )
    await adapter.send_message(chat_id, text)


def _ensure_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        Path(database_url[len(prefix) :]).parent.mkdir(parents=True, exist_ok=True)
