from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from raman.settings import RamanSettings

WEBHOOK_PATH = "/telegram/webhook"
SUPPORTED_TELEGRAM_PORTS = {80, 88, 443, 8443}


def normalize_public_base_url(raw_url: str) -> str:
    value = raw_url.strip().rstrip("/")
    if value.endswith(WEBHOOK_PATH):
        value = value[: -len(WEBHOOK_PATH)].rstrip("/")
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.scheme != "https":
        raise ValueError("Telegram webhooks require an https:// public URL.")
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        raise ValueError("Telegram cannot call localhost; use an HTTPS tunnel URL.")
    if parts.path not in {"", "/"}:
        raise ValueError(
            "Pass the ngrok base URL only, or the exact /telegram/webhook URL."
        )
    if parts.port is not None and parts.port not in SUPPORTED_TELEGRAM_PORTS:
        raise ValueError("Telegram supports webhook ports 443, 80, 88, and 8443.")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def webhook_url(public_base_url: str) -> str:
    return f"{normalize_public_base_url(public_base_url)}{WEBHOOK_PATH}"


def build_set_webhook_request(
    settings: RamanSettings,
    public_base_url: str,
    *,
    drop_pending_updates: bool,
) -> Request:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not settings.telegram_webhook_secret:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is required.")
    body = urlencode(
        {
            "url": webhook_url(public_base_url),
            "secret_token": settings.telegram_webhook_secret,
            "drop_pending_updates": "true" if drop_pending_updates else "false",
        }
    ).encode("utf-8")
    return Request(
        f"{settings.telegram_api_base_url.rstrip('/')}"
        f"/bot{settings.telegram_bot_token}/setWebhook",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )


def check_health(public_base_url: str, *, timeout: float) -> None:
    request = Request(f"{normalize_public_base_url(public_base_url)}/healthz")
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload != {"status": "ok"}:
        raise RuntimeError(f"Unexpected /healthz response: {payload!r}")


def set_webhook(
    settings: RamanSettings,
    public_base_url: str,
    *,
    drop_pending_updates: bool,
    timeout: float,
) -> dict[str, Any]:
    request = build_set_webhook_request(
        settings,
        public_base_url,
        drop_pending_updates=drop_pending_updates,
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Point the Raman Telegram webhook at a local HTTPS tunnel."
    )
    parser.add_argument(
        "public_base_url",
        help="ngrok HTTPS base URL, or the full /telegram/webhook URL.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Env file containing Telegram secrets. Defaults to .env.",
    )
    parser.add_argument(
        "--no-drop-pending",
        action="store_false",
        dest="drop_pending_updates",
        help="Do not ask Telegram to discard pending updates when switching.",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Set the webhook without checking <public-base-url>/healthz first.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Network timeout in seconds. Defaults to 10.",
    )
    args = parser.parse_args(argv)

    try:
        base_url = normalize_public_base_url(args.public_base_url)
        settings = RamanSettings(_env_file=args.env_file)
        if not args.skip_health_check:
            check_health(base_url, timeout=args.timeout)
        result = set_webhook(
            settings,
            base_url,
            drop_pending_updates=args.drop_pending_updates,
            timeout=args.timeout,
        )
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        print(f"Failed to set Raman local webhook: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "webhook_url": webhook_url(base_url),
                "telegram_result": result,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
