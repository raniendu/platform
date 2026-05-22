#!/usr/bin/env python3
"""Validate Pushover credentials from environment-provided secrets."""

from __future__ import annotations

import os

import httpx

from prefect.blocks.system import Secret

PUSHOVER_VALIDATE_URL = "https://api.pushover.net/1/users/validate.json"
PUSHOVER_APP_TOKEN_BLOCK = "pushover-app-token"
PUSHOVER_USER_KEY_BLOCK = "pushover-user-key"


def get_pushover_credentials_from_env() -> tuple[str, str] | None:
    """Return Pushover credentials from environment variables if both are set."""
    app_token = os.getenv("PUSHOVER_APP_TOKEN", "").strip()
    user_key = os.getenv("PUSHOVER_USER_KEY", "").strip()

    if not app_token:
        print(
            "✗ PUSHOVER_APP_TOKEN is not set. "
            "Set the GitHub repository secret and redeploy."
        )
        return None

    if not user_key:
        print(
            "✗ PUSHOVER_USER_KEY is not set. "
            "Set the GitHub repository secret and redeploy."
        )
        return None

    return app_token, user_key


def validate_pushover_credentials(app_token: str, user_key: str) -> int:
    """Validate Pushover credentials against the Pushover API."""

    # Validate credentials against the Pushover API
    try:
        response = httpx.post(
            PUSHOVER_VALIDATE_URL,
            data={"token": app_token, "user": user_key},
            timeout=10,
        )
        result = response.json()

        if result.get("status") == 1:
            print("✅ Pushover credentials are valid")
            return 0

        errors = result.get("errors", ["Unknown error"])
        print(f"✗ Pushover credential validation failed: {', '.join(errors)}")
        return 1

    except httpx.HTTPError as exc:
        print(f"✗ Could not reach Pushover API: {exc}")
        return 1


def save_pushover_secret_blocks(app_token: str, user_key: str) -> int:
    """Save Pushover credentials as Prefect Secret blocks."""
    try:
        Secret(value=app_token).save(PUSHOVER_APP_TOKEN_BLOCK, overwrite=True)
        print(f"✓ Saved Prefect Secret block: {PUSHOVER_APP_TOKEN_BLOCK}")
        Secret(value=user_key).save(PUSHOVER_USER_KEY_BLOCK, overwrite=True)
        print(f"✓ Saved Prefect Secret block: {PUSHOVER_USER_KEY_BLOCK}")
        return 0
    except Exception as exc:
        print(f"✗ Could not save Prefect Secret blocks: {type(exc).__name__}")
        return 1


def main() -> int:
    credentials = get_pushover_credentials_from_env()
    if credentials is None:
        return 1

    app_token, user_key = credentials
    if validate_pushover_credentials(app_token, user_key) != 0:
        return 1

    return save_pushover_secret_blocks(app_token, user_key)


if __name__ == "__main__":
    raise SystemExit(main())
