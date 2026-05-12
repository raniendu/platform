from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from cloudevents.v1.http.event import CloudEvent

from homi.agent import build_agent_runner
from homi.settings import HomiSettings
from homi.spec import load_spec


@dataclass(frozen=True)
class ThreadRecord:
    interface: str
    external_thread_id: str
    agent_name: str
    message_history_json: bytes | None


@dataclass(frozen=True)
class InboundMessage:
    interface: str
    external_thread_id: str
    prompt: str
    agent_name: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationReply:
    interface: str
    external_thread_id: str
    agent_name: str
    output: str


@dataclass(frozen=True)
class EnqueuedEvent:
    workflow_id: str
    status: str


class RunnableAgent(Protocol):
    async def run(
        self,
        user_prompt: str,
        *,
        message_history_json: bytes | None,
        conversation_id: str,
    ) -> Any: ...


AgentFactory = Callable[[str], RunnableAgent]
MessageEnqueuer = Callable[[InboundMessage], Awaitable[EnqueuedEvent]]


class ThreadStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    interface TEXT NOT NULL,
                    external_thread_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    message_history_json BLOB,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (interface, external_thread_id)
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telegram_updates (
                    update_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """)

    def get_thread(
        self,
        interface: str,
        external_thread_id: str,
        *,
        default_agent: str,
    ) -> ThreadRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT interface, external_thread_id, agent_name, message_history_json
                FROM threads
                WHERE interface = ? AND external_thread_id = ?
                """,
                (interface, external_thread_id),
            ).fetchone()
        if row is None:
            return ThreadRecord(interface, external_thread_id, default_agent, None)
        history = row["message_history_json"]
        return ThreadRecord(
            interface=row["interface"],
            external_thread_id=row["external_thread_id"],
            agent_name=row["agent_name"],
            message_history_json=bytes(history) if history is not None else None,
        )

    def set_history(
        self,
        interface: str,
        external_thread_id: str,
        *,
        agent_name: str,
        message_history_json: bytes,
    ) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO threads (
                    interface,
                    external_thread_id,
                    agent_name,
                    message_history_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(interface, external_thread_id) DO UPDATE SET
                    agent_name = excluded.agent_name,
                    message_history_json = excluded.message_history_json,
                    updated_at = excluded.updated_at
                """,
                (
                    interface,
                    external_thread_id,
                    agent_name,
                    message_history_json,
                    now,
                    now,
                ),
            )

    def set_agent(
        self, interface: str, external_thread_id: str, agent_name: str
    ) -> None:
        thread = self.get_thread(
            interface, external_thread_id, default_agent=agent_name
        )
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO threads (
                    interface,
                    external_thread_id,
                    agent_name,
                    message_history_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(interface, external_thread_id) DO UPDATE SET
                    agent_name = excluded.agent_name,
                    updated_at = excluded.updated_at
                """,
                (
                    interface,
                    external_thread_id,
                    agent_name,
                    thread.message_history_json,
                    now,
                    now,
                ),
            )

    def reset_history(self, interface: str, external_thread_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE threads
                SET message_history_json = NULL, updated_at = ?
                WHERE interface = ? AND external_thread_id = ?
                """,
                (_utc_now(), interface, external_thread_id),
            )

    def claim_telegram_update(self, update_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO telegram_updates (update_id, created_at)
                VALUES (?, ?)
                """,
                (update_id, _utc_now()),
            )
        return cursor.rowcount == 1


class ConversationService:
    def __init__(
        self,
        *,
        settings: HomiSettings,
        store: ThreadStore,
        agent_factory: AgentFactory | None = None,
    ):
        self.settings = settings
        self.store = store
        self._agent_factory = agent_factory
        self._agent_cache: dict[str, RunnableAgent] = {}

    async def send_message(self, message: InboundMessage) -> ConversationReply:
        thread = self.store.get_thread(
            message.interface,
            message.external_thread_id,
            default_agent=self.settings.default_agent,
        )
        agent_name = message.agent_name or thread.agent_name
        agent = self._get_agent(agent_name)
        result = await agent.run(
            message.prompt,
            message_history_json=thread.message_history_json,
            conversation_id=f"{message.interface}:{message.external_thread_id}",
        )
        self.store.set_history(
            message.interface,
            message.external_thread_id,
            agent_name=agent_name,
            message_history_json=result.message_history_json,
        )
        return ConversationReply(
            interface=message.interface,
            external_thread_id=message.external_thread_id,
            agent_name=agent_name,
            output=str(result.output),
        )

    def _get_agent(self, name: str) -> RunnableAgent:
        if self._agent_factory is not None:
            return self._agent_factory(name)
        if name not in self._agent_cache:
            spec = load_spec(name, self.settings.spec_root)
            self._agent_cache[name] = build_agent_runner(
                spec=spec, settings=self.settings
            )
        return self._agent_cache[name]


def make_message_received_event(message: InboundMessage) -> CloudEvent:
    return CloudEvent(
        {
            "type": "homi.message.received",
            "source": f"/interfaces/{message.interface}/threads/{message.external_thread_id}",
            "subject": message.external_thread_id,
            "datacontenttype": "application/json",
        },
        {
            "interface": message.interface,
            "external_thread_id": message.external_thread_id,
            "prompt": message.prompt,
            "agent_name": message.agent_name,
            "metadata": message.metadata,
        },
    )


def make_reply_requested_event(
    message: InboundMessage, reply: ConversationReply
) -> CloudEvent:
    return CloudEvent(
        {
            "type": "homi.message.reply_requested",
            "source": f"/interfaces/{reply.interface}/threads/{reply.external_thread_id}",
            "subject": reply.external_thread_id,
            "datacontenttype": "application/json",
        },
        {
            "interface": reply.interface,
            "external_thread_id": reply.external_thread_id,
            "agent_name": reply.agent_name,
            "output": reply.output,
            "metadata": message.metadata,
        },
    )


def cloud_event_to_dict(event: CloudEvent) -> dict[str, Any]:
    return {
        "attributes": dict(event.get_attributes()),
        "data": event.get_data(),
    }


def cloud_event_from_dict(value: dict[str, Any]) -> CloudEvent:
    return CloudEvent(value["attributes"], value.get("data"))


def inbound_message_from_event(event: CloudEvent) -> InboundMessage:
    data = event.get_data()
    if not isinstance(data, dict):
        raise ValueError("CloudEvent data must be an object")
    return InboundMessage(
        interface=str(data["interface"]),
        external_thread_id=str(data["external_thread_id"]),
        prompt=str(data["prompt"]),
        agent_name=data.get("agent_name"),
        metadata=dict(data.get("metadata") or {}),
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
