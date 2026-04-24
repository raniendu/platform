#!/usr/bin/env python3
"""Validate Pushover credentials from environment-provided secrets."""

from __future__ import annotations

import os

import httpx

PUSHOVER_VALIDATE_URL = "https://api.pushover.net/1/users/validate.json"


def validate_pushover_credentials() -> int:
    """Validate PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY are set and valid."""
    app_token = os.getenv("PUSHOVER_APP_TOKEN", "").strip()
    user_key = os.getenv("PUSHOVER_USER_KEY", "").strip()

    if not app_token:
        print(
            "✗ PUSHOVER_APP_TOKEN is not set. "
            "Set the GitHub repository secret and redeploy."
        )
        return 1

    if not user_key:
        print(
            "✗ PUSHOVER_USER_KEY is not set. "
            "Set the GitHub repository secret and redeploy."
        )
        return 1

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


def main() -> int:
    return validate_pushover_credentials()


if __name__ == "__main__":
    raise SystemExit(main())
