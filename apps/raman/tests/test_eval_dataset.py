from pydantic_ai.models.test import TestModel

from evals.dataset import build_dataset
from evals.run import iter_eval_specs
from raman.settings import RamanSettings


def test_eval_specs_include_every_real_agent():
    settings = RamanSettings(_env_file=None)

    specs = list(iter_eval_specs(settings.spec_root))

    assert [spec.name for spec in specs] == ["Gobind", "Leo", "Raman"]


def test_build_dataset_adds_agent_specific_cases():
    model = TestModel()

    cases_by_agent = {
        "Gobind": "health_safety_boundary",
        "Leo": "financial_advice_boundary",
        "Raman": "unavailable_tools_boundary",
    }

    for agent_name, expected_case in cases_by_agent.items():
        dataset = build_dataset(judge_model=model, agent_name=agent_name)

        assert expected_case in {case.name for case in dataset.cases}
