import os

import pytest

from evals.dataset import build_dataset
from evals.run import iter_eval_specs
from raman.agent import build_agent
from raman.settings import RamanSettings, build_model

pytestmark = pytest.mark.skipif(
    os.getenv("RAMAN_RUN_EVALS") != "1",
    reason="Set RAMAN_RUN_EVALS=1 to run live evals against the configured model.",
)


@pytest.mark.parametrize(
    "spec",
    list(iter_eval_specs(RamanSettings(_env_file=None).spec_root)),
    ids=lambda spec: spec.name,
)
async def test_eval_dataset_passes(spec):
    settings = RamanSettings()
    agent = build_agent(spec=spec, settings=settings)
    judge_model = build_model(settings)
    dataset = build_dataset(judge_model=judge_model, agent_name=spec.name)

    async def task(prompt: str) -> str:
        result = await agent.run(prompt)
        return str(result.output)

    report = await dataset.evaluate(task)

    failures = [
        case for case in report.cases if any(not a.value for a in case.assertions)
    ]
    assert not failures, f"Eval failures: {[c.name for c in failures]}"
