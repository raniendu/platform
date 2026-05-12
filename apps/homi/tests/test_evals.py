import os

import pytest

from homi.agent import build_agent_runner
from homi.settings import HomiSettings
from homi.spec import load_spec

pytestmark = pytest.mark.skipif(
    os.getenv("HOMI_RUN_EVALS") != "1",
    reason="Set HOMI_RUN_EVALS=1 to run live evals against Bedrock.",
)


async def test_live_identity_smoke():
    settings = HomiSettings()
    spec = load_spec(settings.default_agent, settings.spec_root)
    runner = build_agent_runner(spec=spec, settings=settings)

    result = await runner.run(
        "What is your name?",
        message_history_json=None,
        conversation_id="eval:homi",
    )

    assert spec.name.lower() in result.output.lower()
