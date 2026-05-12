from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from strands import Agent

from homi.context import agent_identity, current_datetime
from homi.settings import HomiSettings, build_model
from homi.spec import AgentSpec, load_spec
from homi.tools import TOOL_REGISTRY


@dataclass(frozen=True)
class RuntimeAgentResult:
    output: str
    message_history_json: bytes


def build_agent(
    spec: AgentSpec | None = None,
    settings: HomiSettings | None = None,
    *,
    messages: list[dict[str, Any]] | None = None,
) -> Agent:
    settings = settings or HomiSettings()
    spec = spec or load_spec(settings.default_agent, settings.spec_root)
    return Agent(
        model=build_model(settings, **spec.model_settings),
        name=spec.name,
        description=spec.description,
        system_prompt=_instructions(spec),
        tools=[TOOL_REGISTRY[name] for name in spec.tools],
        messages=messages or [],
    )


class HomiAgentRunner:
    def __init__(self, *, spec: AgentSpec, settings: HomiSettings):
        self.spec = spec
        self.settings = settings

    async def run(
        self,
        user_prompt: str,
        *,
        message_history_json: bytes | None,
        conversation_id: str,
    ) -> RuntimeAgentResult:
        del conversation_id
        agent = build_agent(
            spec=self.spec,
            settings=self.settings,
            messages=_load_messages(message_history_json),
        )
        result = await agent.invoke_async(user_prompt)
        return RuntimeAgentResult(
            output=str(result),
            message_history_json=_dump_messages(agent.messages),
        )


def build_agent_runner(
    spec: AgentSpec | None = None,
    settings: HomiSettings | None = None,
) -> HomiAgentRunner:
    settings = settings or HomiSettings()
    spec = spec or load_spec(settings.default_agent, settings.spec_root)
    return HomiAgentRunner(spec=spec, settings=settings)


def _instructions(spec: AgentSpec) -> str:
    return "\n\n".join(
        [
            spec.instructions,
            agent_identity(spec.name),
            current_datetime(),
        ]
    )


def _load_messages(message_history_json: bytes | None) -> list[dict[str, Any]]:
    if not message_history_json:
        return []
    value = json.loads(message_history_json.decode("utf-8"))
    if not isinstance(value, list):
        raise ValueError("Homi message history must be a JSON list")
    return value


def _dump_messages(messages: Any) -> bytes:
    return json.dumps(messages, default=_json_default).encode("utf-8")


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)
