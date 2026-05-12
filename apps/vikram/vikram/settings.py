from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VikramSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    model: str = Field(
        default="gemini-flash-latest",
        validation_alias="VIKRAM_MODEL",
    )
    spec_root: Path = Field(
        default=Path(__file__).resolve().parent.parent / "spec",
        validation_alias="VIKRAM_SPEC_ROOT",
    )
    default_agent: str = Field(default="vikram", validation_alias="VIKRAM_AGENT")
    parallel_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VIKRAM_PARALLEL_API_KEY", "PARALLEL_API_KEY"),
    )
    vikram_db_path: Path = Field(
        default=Path(__file__).resolve().parent.parent / ".vikram" / "vikram.sqlite3",
        validation_alias="VIKRAM_DB_PATH",
    )
    adk_session_database_url: str | None = Field(
        default=None,
        validation_alias="VIKRAM_ADK_SESSION_DATABASE_URL",
    )
    dbos_system_database_url: str | None = Field(
        default=None,
        validation_alias="VIKRAM_DBOS_SYSTEM_DATABASE_URL",
    )
    public_base_url: str | None = Field(
        default=None, validation_alias="VIKRAM_PUBLIC_BASE_URL"
    )
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias="VIKRAM_TELEGRAM_BOT_TOKEN",
    )
    telegram_webhook_secret: str | None = Field(
        default=None,
        validation_alias="VIKRAM_TELEGRAM_WEBHOOK_SECRET",
    )
    telegram_allowed_chat_ids: str = Field(
        default="",
        validation_alias="VIKRAM_TELEGRAM_ALLOWED_CHAT_IDS",
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org",
        validation_alias="VIKRAM_TELEGRAM_API_BASE_URL",
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
        return f"sqlite:///{self.vikram_db_path.parent / 'dbos.sqlite3'}"

    @property
    def effective_adk_session_database_url(self) -> str:
        if self.adk_session_database_url:
            return self.adk_session_database_url
        return f"sqlite+aiosqlite:///{self.vikram_db_path.parent / 'adk_sessions.sqlite3'}"
