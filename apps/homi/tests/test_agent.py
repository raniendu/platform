import pytest

from homi.agent import HomiAgentRunner, build_agent, build_agent_runner
from homi.settings import HomiSettings
from homi.spec import load_spec

HOMI_ENV_VARS = (
    "HOMI_MODEL_ID",
    "HOMI_AWS_REGION",
    "HOMI_SPEC_ROOT",
    "HOMI_AGENT",
    "HOMI_PARALLEL_API_KEY",
    "PARALLEL_API_KEY",
)


def clean_settings(monkeypatch, **overrides) -> HomiSettings:
    for env_var in HOMI_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    return HomiSettings(_env_file=None, **overrides)


def test_settings_default_to_bedrock_sonnet(monkeypatch):
    settings = clean_settings(monkeypatch)

    assert settings.model_id == "us.anthropic.claude-sonnet-4-20250514-v1:0"
    assert settings.aws_region == "us-west-2"
    assert settings.default_agent == "homi"


def test_prefixed_parallel_api_key_wins(monkeypatch):
    monkeypatch.setenv("PARALLEL_API_KEY", "shared")
    monkeypatch.setenv("HOMI_PARALLEL_API_KEY", "homi")

    assert HomiSettings(_env_file=None).parallel_api_key == "homi"


def test_build_agent_passes_spec_to_strands(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.name = kwargs["name"]

    monkeypatch.setattr("homi.agent.Agent", FakeAgent)
    monkeypatch.setattr("homi.agent.build_model", lambda settings, **kwargs: "model")

    agent = build_agent(settings=clean_settings(monkeypatch))

    assert agent.name == "homi"
    assert captured["model"] == "model"
    assert captured["description"] == "Personal assistant agent for Raniendu."
    assert captured["messages"] == []
    assert "Your name is homi." in captured["system_prompt"]


def test_build_agent_runner_uses_requested_spec(monkeypatch):
    settings = clean_settings(monkeypatch)
    spec = load_spec("homi", settings.spec_root)

    runner = build_agent_runner(spec=spec, settings=settings)

    assert isinstance(runner, HomiAgentRunner)
    assert runner.spec.name == "homi"


@pytest.mark.asyncio
async def test_runner_persists_strands_messages(monkeypatch):
    class FakeAgent:
        def __init__(self, **kwargs):
            self.messages = list(kwargs["messages"])

        async def invoke_async(self, prompt):
            self.messages.append({"role": "user", "content": [{"text": prompt}]})
            self.messages.append({"role": "assistant", "content": [{"text": "reply"}]})
            return "reply"

    monkeypatch.setattr("homi.agent.Agent", FakeAgent)
    monkeypatch.setattr("homi.agent.build_model", lambda settings, **kwargs: "model")

    runner = build_agent_runner(settings=clean_settings(monkeypatch))
    result = await runner.run(
        "hello",
        message_history_json=b'[{"role":"user","content":[{"text":"prior"}]}]',
        conversation_id="telegram:123",
    )

    assert result.output == "reply"
    assert b"prior" in result.message_history_json
    assert b"hello" in result.message_history_json
