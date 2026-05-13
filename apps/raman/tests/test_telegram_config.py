from pathlib import Path

import pytest

from raman.telegram_config import load_telegram_config


def write_telegram_config(spec_root: Path, body: str) -> None:
    spec_root.mkdir(parents=True, exist_ok=True)
    (spec_root / "telegram.toml").write_text(body)


def test_load_telegram_config_resolves_bot_env_values(monkeypatch, tmp_path):
    spec_root = tmp_path / "spec"
    write_telegram_config(
        spec_root,
        """
default_bot = "raman"

[[bots]]
name = "raman"
default_agent = "raman"
token_env = "RAMAN_TELEGRAM_BOT_TOKEN"
webhook_secret_env = "RAMAN_TELEGRAM_WEBHOOK_SECRET"
allowed_chat_ids_env = "RAMAN_TELEGRAM_ALLOWED_CHAT_IDS"
api_base_url_env = "RAMAN_TELEGRAM_API_BASE_URL"
""",
    )
    monkeypatch.setenv("RAMAN_TELEGRAM_BOT_TOKEN", "token-a")
    monkeypatch.setenv("RAMAN_TELEGRAM_WEBHOOK_SECRET", "secret-a")
    monkeypatch.setenv("RAMAN_TELEGRAM_ALLOWED_CHAT_IDS", "123,-100123")
    monkeypatch.setenv("RAMAN_TELEGRAM_API_BASE_URL", "https://telegram.test")

    config = load_telegram_config(spec_root)
    bot = config.get_bot("raman")

    assert config.default_bot_name == "raman"
    assert bot.name == "raman"
    assert bot.default_agent == "raman"
    assert bot.bot_token == "token-a"
    assert bot.webhook_secret == "secret-a"
    assert bot.allowed_chat_id_set == {123, -100123}
    assert bot.api_base_url == "https://telegram.test"
    assert bot.webhook_path == "/telegram/raman/webhook"


def test_load_telegram_config_rejects_duplicate_bot_names(monkeypatch, tmp_path):
    spec_root = tmp_path / "spec"
    write_telegram_config(
        spec_root,
        """
default_bot = "raman"

[[bots]]
name = "raman"
default_agent = "raman"
token_env = "BOT_TOKEN"
webhook_secret_env = "BOT_SECRET"
allowed_chat_ids_env = "BOT_CHAT_IDS"

[[bots]]
name = "raman"
default_agent = "other"
token_env = "OTHER_BOT_TOKEN"
webhook_secret_env = "OTHER_BOT_SECRET"
allowed_chat_ids_env = "OTHER_BOT_CHAT_IDS"
""",
    )
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("BOT_SECRET", "secret")
    monkeypatch.setenv("BOT_CHAT_IDS", "123")
    monkeypatch.setenv("OTHER_BOT_TOKEN", "token")
    monkeypatch.setenv("OTHER_BOT_SECRET", "secret")
    monkeypatch.setenv("OTHER_BOT_CHAT_IDS", "123")

    with pytest.raises(ValueError, match="Duplicate Telegram bot name"):
        load_telegram_config(spec_root)


def test_load_telegram_config_falls_back_to_legacy_single_bot(monkeypatch, tmp_path):
    spec_root = tmp_path / "spec"
    spec_root.mkdir()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "legacy-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "legacy-secret")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123")

    config = load_telegram_config(spec_root)
    bot = config.get_default_bot()

    assert config.default_bot_name == "telegram"
    assert bot.name == "telegram"
    assert bot.default_agent == "raman"
    assert bot.bot_token == "legacy-token"
    assert bot.webhook_secret == "legacy-secret"
    assert bot.allowed_chat_id_set == {123}
    assert bot.webhook_path == "/telegram/webhook"
