from urllib.parse import parse_qs

import pytest

from raman.local_webhook import (
    build_set_webhook_request,
    normalize_public_base_url,
    webhook_url,
)
from raman.settings import RamanSettings
from raman.telegram_config import TelegramBotConfig


def test_normalize_public_base_url_accepts_ngrok_base_url():
    base_url = normalize_public_base_url("https://abc123.ngrok-free.app/")

    assert base_url == "https://abc123.ngrok-free.app"
    assert webhook_url(base_url) == "https://abc123.ngrok-free.app/telegram/webhook"
    assert (
        webhook_url(base_url, bot_name="research")
        == "https://abc123.ngrok-free.app/telegram/research/webhook"
    )


def test_normalize_public_base_url_accepts_full_webhook_url():
    base_url = normalize_public_base_url(
        "https://abc123.ngrok-free.app/telegram/webhook"
    )

    assert base_url == "https://abc123.ngrok-free.app"


def test_normalize_public_base_url_accepts_full_named_webhook_url():
    base_url = normalize_public_base_url(
        "https://abc123.ngrok-free.app/telegram/research/webhook"
    )

    assert base_url == "https://abc123.ngrok-free.app"


@pytest.mark.parametrize(
    "url",
    [
        "http://abc123.ngrok-free.app",
        "https://localhost:8000",
        "https://127.0.0.1:8000",
        "https://abc123.ngrok-free.app/custom/path",
    ],
)
def test_normalize_public_base_url_rejects_bad_local_webhook_urls(url):
    with pytest.raises(ValueError):
        normalize_public_base_url(url)


def test_build_set_webhook_request_uses_form_body_without_printing_secret():
    settings = RamanSettings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="bot-token",
        TELEGRAM_WEBHOOK_SECRET="secret-token",
    )

    request = build_set_webhook_request(
        settings,
        "https://abc123.ngrok-free.app",
        drop_pending_updates=True,
    )

    body = parse_qs(request.data.decode("utf-8"))
    assert request.full_url == "https://api.telegram.org/botbot-token/setWebhook"
    assert body == {
        "url": ["https://abc123.ngrok-free.app/telegram/webhook"],
        "secret_token": ["secret-token"],
        "drop_pending_updates": ["true"],
    }


def test_build_set_webhook_request_uses_selected_bot():
    bot = TelegramBotConfig(
        name="research",
        default_agent="research",
        bot_token="bot-token",
        webhook_secret="secret-token",
        allowed_chat_ids="123",
        api_base_url="https://api.telegram.org",
    )

    request = build_set_webhook_request(
        bot,
        "https://abc123.ngrok-free.app",
        drop_pending_updates=False,
    )

    body = parse_qs(request.data.decode("utf-8"))
    assert request.full_url == "https://api.telegram.org/botbot-token/setWebhook"
    assert body == {
        "url": ["https://abc123.ngrok-free.app/telegram/research/webhook"],
        "secret_token": ["secret-token"],
        "drop_pending_updates": ["false"],
    }
