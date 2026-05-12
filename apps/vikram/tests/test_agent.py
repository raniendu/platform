from dataclasses import dataclass

import pytest

from vikram.agent import (
    VikramAgentRunner,
    build_agent,
    build_agent_runner,
    _load_session_ref,
)
from vikram.settings import VikramSettings
from vikram.spec import load_spec

VIKRAM_ENV_VARS = (
    "VIKRAM_MODEL",
    "VIKRAM_SPEC_ROOT",
    "VIKRAM_AGENT",
    "VIKRAM_PARALLEL_API_KEY",
    "PARALLEL_API_KEY",
)


def clean_settings(monkeypatch, **overrides) -> VikramSettings:
    for env_var in VIKRAM_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    return VikramSettings(_env_file=None, **overrides)


def test_settings_default_to_gemini(monkeypatch):
    settings = clean_settings(monkeypatch)

    assert settings.model == "gemini-flash-latest"
    assert settings.default_agent == "vikram"
    assert settings.effective_adk_session_database_url.endswith("adk_sessions.sqlite3")


def test_prefixed_parallel_api_key_wins(monkeypatch):
    monkeypatch.setenv("PARALLEL_API_KEY", "shared")
    monkeypatch.setenv("VIKRAM_PARALLEL_API_KEY", "vikram")

    assert VikramSettings(_env_file=None).parallel_api_key == "vikram"


def test_build_agent_passes_spec_to_adk(monkeypatch):
    captured = {}

    class FakeLlmAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.name = kwargs["name"]

    monkeypatch.setattr("vikram.agent.LlmAgent", FakeLlmAgent)

    agent = build_agent(settings=clean_settings(monkeypatch, VIKRAM_MODEL="gemini-test"))

    assert agent.name == "vikram"
    assert captured["model"] == "gemini-test"
    assert captured["description"] == "Personal assistant agent for Raniendu."
    assert "Your name is vikram." in captured["instruction"]


def test_build_agent_runner_uses_requested_spec(monkeypatch):
    settings = clean_settings(monkeypatch)
    spec = load_spec("vikram", settings.spec_root)

    runner = build_agent_runner(spec=spec, settings=settings)

    assert isinstance(runner, VikramAgentRunner)
    assert runner.spec.name == "vikram"


def test_load_session_ref_reuses_persisted_session():
    session_ref = _load_session_ref(
        b'{"session_id":"session-1","user_id":"telegram_123"}',
        "telegram:123",
    )

    assert session_ref == {"session_id": "session-1", "user_id": "telegram_123"}


@pytest.mark.asyncio
async def test_runner_uses_database_session_service(monkeypatch, tmp_path):
    calls = []

    class FakeSessionService:
        def __init__(self, *, db_url):
            calls.append(("db", db_url))

        async def get_session(self, *, app_name, user_id, session_id):
            calls.append(("get", app_name, user_id, session_id))
            return None

        async def create_session(self, *, app_name, user_id, session_id):
            calls.append(("create", app_name, user_id, session_id))

    @dataclass
    class FakePart:
        text: str

    @dataclass
    class FakeContent:
        parts: list[FakePart]

    class FakeEvent:
        content = FakeContent(parts=[FakePart(text="reply")])

        def is_final_response(self):
            return True

    class FakeRunner:
        def __init__(self, *, agent, app_name, session_service):
            calls.append(("runner", agent.name, app_name, session_service.__class__.__name__))

        async def run_async(self, *, user_id, session_id, new_message):
            calls.append(("run", user_id, session_id, new_message.parts[0].text))
            yield FakeEvent()

    class FakeTypes:
        @dataclass
        class Part:
            text: str

        @dataclass
        class Content:
            role: str
            parts: list["FakeTypes.Part"]

    class FakeLlmAgent:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]

    monkeypatch.setattr("vikram.agent.DatabaseSessionService", FakeSessionService)
    monkeypatch.setattr("vikram.agent.Runner", FakeRunner)
    monkeypatch.setattr("vikram.agent.types", FakeTypes)
    monkeypatch.setattr("vikram.agent.LlmAgent", FakeLlmAgent)

    settings = clean_settings(
        monkeypatch,
        VIKRAM_ADK_SESSION_DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'adk.sqlite3'}",
    )
    runner = build_agent_runner(settings=settings)
    result = await runner.run(
        "hello",
        message_history_json=b'{"session_id":"session-1","user_id":"telegram_123"}',
        conversation_id="telegram:123",
    )

    assert result.output == "reply"
    assert b"session-1" in result.message_history_json
    assert ("run", "telegram_123", "session-1", "hello") in calls
