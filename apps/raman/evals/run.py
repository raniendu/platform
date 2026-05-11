from __future__ import annotations

import asyncio

from evals.dataset import build_dataset
from raman.agent import build_agent
from raman.settings import RamanSettings, build_model
from raman.spec import load_spec


async def main() -> None:
    settings = RamanSettings()
    spec = load_spec(settings.default_agent, settings.spec_root)
    agent = build_agent(spec=spec, settings=settings)
    judge_model = build_model(settings)
    dataset = build_dataset(judge_model=judge_model, agent_name=spec.name)

    async def task(prompt: str) -> str:
        result = await agent.run(prompt)
        return str(result.output)

    report = await dataset.evaluate(task)
    report.print(include_input=True, include_output=True)


if __name__ == "__main__":
    asyncio.run(main())
