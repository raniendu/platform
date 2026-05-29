from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_ai.models import Model
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_settings import BaseSettings, SettingsConfigDict

ModelProvider = Literal["ollama", "digitalocean"]


def _resolve_spec_root(package_relative: Path) -> Path:
    """Locate spec/ for both dev (in-checkout) and installed (`uv tool`) layouts.

    Dev: ``<package>/../spec`` exists as a sibling of the package.
    Installed: package lives in site-packages; spec ships separately, so we
    fall back to the source checkout recorded by ``install.sh`` at
    ``~/.config/raman/install.toml``.
    """
    if package_relative.is_dir():
        return package_relative
    try:
        from raman.update import load_metadata
    except Exception:
        return package_relative
    source_dir = load_metadata().get("source_dir")
    if source_dir:
        candidate = Path(str(source_dir)) / "apps" / "raman" / "spec"
        if candidate.is_dir():
            return candidate
    return package_relative


def _default_spec_root() -> Path:
    return _resolve_spec_root(Path(__file__).resolve().parent.parent / "spec")


class RamanSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    model_provider: ModelProvider = Field(
        default="ollama", validation_alias="RAMAN_MODEL_PROVIDER"
    )
    dev_model: str = Field(default="gemma4:26b-mlx", validation_alias="RAMAN_DEV_MODEL")
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        validation_alias="OLLAMA_BASE_URL",
    )
    do_inference_api_key: str | None = Field(
        default=None, validation_alias="DO_INFERENCE_API_KEY"
    )
    do_inference_base_url: str = Field(
        default="https://inference.do-ai.run/v1",
        validation_alias="DO_INFERENCE_BASE_URL",
    )
    spec_root: Path = Field(
        default_factory=_default_spec_root,
        validation_alias="RAMAN_SPEC_ROOT",
    )
    default_agent: str = Field(default="raman", validation_alias="RAMAN_AGENT")
    parallel_api_key: str | None = Field(
        default=None, validation_alias="PARALLEL_API_KEY"
    )
    raman_db_path: Path = Field(
        default=Path(__file__).resolve().parent.parent / ".raman" / "raman.sqlite3",
        validation_alias="RAMAN_DB_PATH",
    )
    grocery_list_path: Path = Field(
        default=Path(__file__).resolve().parent.parent
        / ".raman"
        / "grocery_lists.json",
        validation_alias="RAMAN_GROCERY_LIST_PATH",
    )
    dbos_system_database_url: str | None = Field(
        default=None, validation_alias="DBOS_SYSTEM_DATABASE_URL"
    )
    public_base_url: str | None = Field(
        default=None, validation_alias="RAMAN_PUBLIC_BASE_URL"
    )
    telegram_bot_token: str | None = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_webhook_secret: str | None = Field(
        default=None, validation_alias="TELEGRAM_WEBHOOK_SECRET"
    )
    telegram_allowed_chat_ids: str = Field(
        default="", validation_alias="TELEGRAM_ALLOWED_CHAT_IDS"
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org", validation_alias="TELEGRAM_API_BASE_URL"
    )
    log_level: str = Field(default="INFO", validation_alias="RAMAN_LOG_LEVEL")
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    observability_enabled: bool = Field(
        default=False, validation_alias="RAMAN_OBSERVABILITY_ENABLED"
    )
    observability_service_name: str = Field(
        default="raman", validation_alias="RAMAN_OBSERVABILITY_SERVICE_NAME"
    )
    observability_otlp_endpoint: str | None = Field(
        default=None, validation_alias="RAMAN_OTLP_ENDPOINT"
    )
    observability_capture_message_content: bool = Field(
        default=False,
        validation_alias="RAMAN_OBSERVABILITY_CAPTURE_MESSAGE_CONTENT",
    )
    observability_disable_metrics: bool = Field(
        default=False, validation_alias="RAMAN_OBSERVABILITY_DISABLE_METRICS"
    )
    observability_disabled_instrumentors: str = Field(
        default="mistral", validation_alias="RAMAN_OBSERVABILITY_DISABLED_INSTRUMENTORS"
    )
    context_window_tokens: int = Field(
        default=256_000,
        validation_alias="RAMAN_CONTEXT_WINDOW_TOKENS",
    )
    context_warning_ratio: float = Field(
        default=0.85,
        validation_alias="RAMAN_CONTEXT_WARNING_RATIO",
    )

    @property
    def normalized_ollama_base_url(self) -> str:
        base_url = self.ollama_base_url.strip().rstrip("/")
        if base_url.endswith("/v1"):
            return base_url
        return f"{base_url}/v1"

    @property
    def telegram_allowed_chat_id_set(self) -> set[int]:
        chat_ids: set[int] = set()
        for raw in self.telegram_allowed_chat_ids.split(","):
            value = raw.strip()
            if value:
                chat_ids.add(int(value))
        return chat_ids

    @property
    def effective_dbos_system_database_url(self) -> str:
        if self.dbos_system_database_url:
            return self.dbos_system_database_url
        return f"sqlite:///{self.raman_db_path.parent / 'dbos.sqlite3'}"

    @property
    def observability_disabled_instrumentor_list(self) -> list[str] | None:
        values = [
            value.strip()
            for value in self.observability_disabled_instrumentors.split(",")
            if value.strip()
        ]
        return values or None


def build_model(settings: RamanSettings | None = None) -> Model:
    settings = settings or RamanSettings()
    if settings.model_provider == "ollama":
        return OllamaModel(
            settings.dev_model,
            provider=OllamaProvider(base_url=settings.normalized_ollama_base_url),
        )
    if settings.model_provider == "digitalocean":
        if not settings.do_inference_api_key:
            raise RuntimeError(
                "DO_INFERENCE_API_KEY is not set. Add it to .env or the runtime "
                "environment to use the digitalocean model provider."
            )
        return OpenAIChatModel(
            settings.dev_model,
            provider=OpenAIProvider(
                base_url=settings.do_inference_base_url,
                api_key=settings.do_inference_api_key,
            ),
        )
    raise RuntimeError(f"Unknown RAMAN_MODEL_PROVIDER: {settings.model_provider!r}")
