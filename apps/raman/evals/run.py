from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

from evals.dataset import build_dataset
from raman.agent import build_agent
from raman.settings import RamanSettings, build_model
from raman.spec import AgentSpec, load_spec


def iter_eval_specs(spec_root: Path) -> Iterator[AgentSpec]:
    for spec_path in sorted(spec_root.glob("*/agent.toml")):
        yield load_spec(spec_path.parent.name, spec_root)


async def evaluate_spec(spec: AgentSpec, settings: RamanSettings) -> None:
    agent = build_agent(spec=spec, settings=settings)
    judge_model = build_model(settings)
    dataset = build_dataset(judge_model=judge_model, agent_name=spec.name)

    async def task(prompt: str) -> str:
        result = await agent.run(prompt)
        return str(result.output)

    print(f"\n=== {spec.name} ===")
    report = await dataset.evaluate(task)
    report.print(include_input=True, include_output=True)


async def main() -> None:
    settings = RamanSettings()
    specs = list(iter_eval_specs(settings.spec_root))
    if not specs:
        raise RuntimeError(f"No agent specs found in {settings.spec_root}")

    for spec in specs:
        await evaluate_spec(spec, settings)


if __name__ == "__main__":
    asyncio.run(main())
