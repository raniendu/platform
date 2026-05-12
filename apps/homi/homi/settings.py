from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HomiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
        validation_alias="HOMI_MODEL_ID",
    )
    aws_region: str = Field(
        default="us-west-2",
        validation_alias=AliasChoices(
            "HOMI_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"
        ),
    )
    spec_root: Path = Field(
        default=Path(__file__).resolve().parent.parent / "spec",
        validation_alias="HOMI_SPEC_ROOT",
    )
    default_agent: str = Field(default="homi", validation_alias="HOMI_AGENT")
    parallel_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HOMI_PARALLEL_API_KEY", "PARALLEL_API_KEY"),
    )
    homi_db_path: Path = Field(
        default=Path(__file__).resolve().parent.parent / ".homi" / "homi.sqlite3",
        validation_alias="HOMI_DB_PATH",
    )
    dbos_system_database_url: str | None = Field(
        default=None,
        validation_alias="HOMI_DBOS_SYSTEM_DATABASE_URL",
    )
    public_base_url: str | None = Field(
        default=None, validation_alias="HOMI_PUBLIC_BASE_URL"
    )
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias="HOMI_TELEGRAM_BOT_TOKEN",
    )
    telegram_webhook_secret: str | None = Field(
        default=None,
        validation_alias="HOMI_TELEGRAM_WEBHOOK_SECRET",
    )
    telegram_allowed_chat_ids: str = Field(
        default="",
        validation_alias="HOMI_TELEGRAM_ALLOWED_CHAT_IDS",
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org",
        validation_alias="HOMI_TELEGRAM_API_BASE_URL",
    )

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
        return f"sqlite:///{self.homi_db_path.parent / 'dbos.sqlite3'}"


def build_model(settings: HomiSettings | None = None, **model_settings: object):
    from strands.models import BedrockModel

    settings = settings or HomiSettings()
    supported_settings = {
        key: value
        for key, value in model_settings.items()
        if key in {"temperature", "top_p", "max_tokens"} and value is not None
    }
    return BedrockModel(
        model_id=settings.model_id,
        region_name=settings.aws_region,
        **supported_settings,
    )
