from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from vikram.context import agent_identity, current_datetime
from vikram.settings import VikramSettings
from vikram.spec import AgentSpec, load_spec
from vikram.tools import TOOL_REGISTRY


@dataclass(frozen=True)
class RuntimeAgentResult:
    output: str
    message_history_json: bytes


def build_agent(
    spec: AgentSpec | None = None,
    settings: VikramSettings | None = None,
) -> LlmAgent:
    settings = settings or VikramSettings()
    spec = spec or load_spec(settings.default_agent, settings.spec_root)
    return LlmAgent(
        model=settings.model,
        name=spec.name,
        description=spec.description,
        instruction=_instructions(spec),
        tools=[TOOL_REGISTRY[name] for name in spec.tools],
    )


class VikramAgentRunner:
    def __init__(self, *, spec: AgentSpec, settings: VikramSettings):
        self.spec = spec
        self.settings = settings

    async def run(
        self,
        user_prompt: str,
        *,
        message_history_json: bytes | None,
        conversation_id: str,
    ) -> RuntimeAgentResult:
        session_ref = _load_session_ref(message_history_json, conversation_id)
        session_service = DatabaseSessionService(
            db_url=self.settings.effective_adk_session_database_url
        )
        await _ensure_session(
            session_service,
            app_name=self.spec.name,
            user_id=session_ref["user_id"],
            session_id=session_ref["session_id"],
        )
        runner = Runner(
            agent=build_agent(spec=self.spec, settings=self.settings),
            app_name=self.spec.name,
            session_service=session_service,
        )
        content = types.Content(role="user", parts=[types.Part(text=user_prompt)])
        final_response_text = "Agent did not produce a final response."
        async for event in runner.run_async(
            user_id=session_ref["user_id"],
            session_id=session_ref["session_id"],
            new_message=content,
        ):
            if event.is_final_response():
                final_response_text = _event_text(event)
                break
        return RuntimeAgentResult(
            output=final_response_text,
            message_history_json=json.dumps(session_ref).encode("utf-8"),
        )


def build_agent_runner(
    spec: AgentSpec | None = None,
    settings: VikramSettings | None = None,
) -> VikramAgentRunner:
    settings = settings or VikramSettings()
    spec = spec or load_spec(settings.default_agent, settings.spec_root)
    return VikramAgentRunner(spec=spec, settings=settings)


def _instructions(spec: AgentSpec) -> str:
    return "\n\n".join(
        [
            spec.instructions,
            agent_identity(spec.name),
            current_datetime(),
        ]
    )


def _load_session_ref(
    message_history_json: bytes | None, conversation_id: str
) -> dict[str, str]:
    if message_history_json:
        value = json.loads(message_history_json.decode("utf-8"))
        if (
            isinstance(value, dict)
            and isinstance(value.get("session_id"), str)
            and isinstance(value.get("user_id"), str)
        ):
            return {"session_id": value["session_id"], "user_id": value["user_id"]}
        raise ValueError("Vikram message history must contain session_id and user_id")
    return {
        "session_id": uuid4().hex,
        "user_id": _safe_identifier(conversation_id),
    }


def _safe_identifier(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)


async def _ensure_session(
    session_service: DatabaseSessionService,
    *,
    app_name: str,
    user_id: str,
    session_id: str,
) -> None:
    existing = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if existing is not None:
        return
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )


def _event_text(event: Any) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None)
    if parts:
        text_blocks = [
            part.text for part in parts if getattr(part, "text", None) is not None
        ]
        if text_blocks:
            return "".join(text_blocks).strip()
    actions = getattr(event, "actions", None)
    if actions and getattr(actions, "escalate", False):
        return f"Agent escalated: {getattr(event, 'error_message', '') or 'No details.'}"
    return "Agent produced a final non-text response."
