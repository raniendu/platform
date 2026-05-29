from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SHARED_DIR_NAME = "shared"


class AgentSurfaceError(RuntimeError):
    """Raised when a spec is loaded on a surface it explicitly disallows."""


class AgentSpec(BaseModel):
    name: str
    description: str
    system_prompt: Path
    cli_only: bool = False
    context_files: list[Path] = []
    skills: list[Path] = []
    shared_context_files: list[Path] = []
    shared_skills: list[Path] = []
    tools: list[str] = []
    model_settings: dict[str, Any] = {}

    agent_dir: Path
    shared_dir: Path

    @property
    def instructions(self) -> str:
        parts = [(self.agent_dir / self.system_prompt).read_text().strip()]
        for ctx in self.shared_context_files:
            parts.append((self.shared_dir / ctx).read_text().strip())
        for ctx in self.context_files:
            parts.append((self.agent_dir / ctx).read_text().strip())
        return "\n\n".join(parts)


def load_spec(name: str, spec_root: Path) -> AgentSpec:
    spec_path = spec_root / name / "agent.toml"
    data = tomllib.loads(spec_path.read_text())
    return AgentSpec(
        **data,
        agent_dir=spec_path.parent,
        shared_dir=spec_root / SHARED_DIR_NAME,
    )


def ensure_surface_allowed(spec: AgentSpec, surface: str) -> None:
    if spec.cli_only and surface != "cli":
        raise AgentSurfaceError(
            f"Agent {spec.name} is CLI-only and cannot run on {surface}."
        )
