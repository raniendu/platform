import os

import pytest

from vikram.agent import build_agent_runner
from vikram.settings import VikramSettings
from vikram.spec import load_spec

pytestmark = pytest.mark.skipif(
    os.getenv("VIKRAM_RUN_EVALS") != "1",
    reason="Set VIKRAM_RUN_EVALS=1 to run live evals against Gemini.",
)


async def test_live_identity_smoke():
    settings = VikramSettings()
    spec = load_spec(settings.default_agent, settings.spec_root)
    runner = build_agent_runner(spec=spec, settings=settings)

    result = await runner.run(
        "What is your name?",
        message_history_json=None,
        conversation_id="eval:vikram",
    )

    assert spec.name.lower() in result.output.lower()
