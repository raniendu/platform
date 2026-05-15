import pytest
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel

from raman.agent import agent, build_agent
from raman.settings import RamanSettings, build_model

RAMAN_ENV_VARS = (
    "RAMAN_DEV_MODEL",
    "OLLAMA_BASE_URL",
    "RAMAN_SPEC_ROOT",
    "RAMAN_AGENT",
    "RAMAN_MODEL_PROVIDER",
    "DO_INFERENCE_API_KEY",
    "DO_INFERENCE_BASE_URL",
)


def clean_settings(monkeypatch, **overrides) -> RamanSettings:
    for env_var in RAMAN_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    return RamanSettings(_env_file=None, **overrides)


def test_agent_is_configured_as_pydantic_ai_agent():
    assert isinstance(agent, Agent)
    assert agent.name == "Raman"


def test_build_agent_uses_requested_settings(monkeypatch):
    local_agent = build_agent(
        settings=clean_settings(
            monkeypatch,
            RAMAN_DEV_MODEL="qwen3",
            OLLAMA_BASE_URL="http://localhost:11434",
        )
    )

    assert isinstance(local_agent, Agent)
    assert local_agent.name == "Raman"
    assert isinstance(local_agent.model, OllamaModel)
    assert local_agent.model.model_name == "qwen3"


def test_settings_default_to_local_ollama(monkeypatch):
    default_settings = clean_settings(monkeypatch)
    model = build_model(default_settings)

    assert isinstance(model, OllamaModel)
    assert model.model_name == "gemma4:26b"
    assert default_settings.normalized_ollama_base_url == "http://localhost:11434/v1"
    assert model.provider.base_url.rstrip("/") == "http://localhost:11434/v1"


def test_build_model_uses_digitalocean_when_provider_is_set(monkeypatch):
    settings = clean_settings(
        monkeypatch,
        RAMAN_MODEL_PROVIDER="digitalocean",
        DO_INFERENCE_API_KEY="do-test-key",
        RAMAN_DEV_MODEL="llama3.3-70b-instruct",
    )
    model = build_model(settings)

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "llama3.3-70b-instruct"
    assert model.provider.base_url.rstrip("/") == "https://inference.do-ai.run/v1"


def test_build_model_digitalocean_requires_api_key(monkeypatch):
    settings = clean_settings(monkeypatch, RAMAN_MODEL_PROVIDER="digitalocean")
    with pytest.raises(RuntimeError, match="DO_INFERENCE_API_KEY"):
        build_model(settings)
