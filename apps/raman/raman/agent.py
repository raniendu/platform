from __future__ import annotations

from pydantic_ai import Agent

from raman.context import agent_identity, current_datetime
from raman.settings import RamanSettings, build_model
from raman.spec import AgentSpec, load_spec
from raman.tools import TOOL_REGISTRY, ToolEntry


class AgentToolError(RuntimeError):
    """Raised when an agent spec references tools unavailable to this package."""


def _resolve_tools(spec: AgentSpec) -> list[ToolEntry]:
    missing = [name for name in spec.tools if name not in TOOL_REGISTRY]
    if missing:
        missing_list = ", ".join(missing)
        raise AgentToolError(
            f"Agent {spec.name} references unknown tool(s): {missing_list}. "
            "The installed Raman package may be stale relative to the agent "
            "specs; run `raman update` or reinstall the raman uv tool."
        )
    return [TOOL_REGISTRY[name] for name in spec.tools]


def build_agent(
    spec: AgentSpec | None = None,
    settings: RamanSettings | None = None,
) -> Agent[None, str]:
    settings = settings or RamanSettings()
    spec = spec or load_spec(settings.default_agent, settings.spec_root)
    tools = _resolve_tools(spec)
    return Agent(
        build_model(settings),
        name=spec.name,
        description=spec.description,
        instructions=[
            spec.instructions,
            agent_identity(spec.name),
            current_datetime,
        ],
        tools=tools,
        model_settings=spec.model_settings or None,
    )


def __getattr__(name: str) -> Agent[None, str]:
    """Lazy module-level ``agent`` so importing this module is side-effect-free.

    The default-agent singleton is built only when something actually reads
    ``raman.agent.agent`` (currently just one test). This keeps fast paths
    like ``raman update`` and ``raman --version`` from triggering a model
    build at import time.
    """
    if name == "agent":
        return build_agent()
    raise AttributeError(f"module 'raman.agent' has no attribute {name!r}")
