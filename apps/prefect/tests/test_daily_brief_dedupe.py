from __future__ import annotations

from datetime import datetime

import pytest

from flows import daily_brief as daily_brief_flow


class _TestLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


def test_repetitive_brief_detected_on_similar_bullet_lines() -> None:
    previous = (
        "• <b>📰 News</b>: India inflation cools and Redmond announces Copilot update\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.2% led by Nvidia"
    )
    candidate = (
        "• <b>📰 News</b>: India inflation cools while Redmond ships Copilot changes\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.1% with Nvidia leading gains"
    )
    assert daily_brief_flow._is_repetitive_brief(candidate, previous) is True


def test_repetitive_brief_not_detected_for_distinct_content() -> None:
    previous = (
        "• <b>📰 News</b>: India inflation cools and Redmond announces Copilot update\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.2% led by Nvidia"
    )
    candidate = (
        "• <b>📰 News</b>: India approves semiconductor subsidy and Redmond opens AI lab\n"
        "• <b>📈 Markets (US)</b>: S&P 500 flat while biotech outperforms"
    )
    assert daily_brief_flow._is_repetitive_brief(candidate, previous) is False


@pytest.mark.asyncio
async def test_load_previous_day_brief_requires_same_period_and_yesterday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 3, 3, 8, 0, tzinfo=daily_brief_flow.PACIFIC_TZ)
    logger = _TestLogger()

    async def fake_aget(name: str, default=None):  # noqa: ANN001
        assert name == "daily-brief-last-morning-v1"
        return {
            "date": "2026-03-02",
            "period": "morning",
            "message": "• Fresh update",
        }

    monkeypatch.setattr(daily_brief_flow.Variable, "aget", staticmethod(fake_aget))

    message = await daily_brief_flow._load_previous_day_brief("morning", now, logger)
    assert message == "• Fresh update"


@pytest.mark.asyncio
async def test_load_previous_day_brief_returns_none_when_missing_or_mismatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 3, 3, 16, 0, tzinfo=daily_brief_flow.PACIFIC_TZ)
    logger = _TestLogger()

    async def fake_aget(name: str, default=None):  # noqa: ANN001
        assert name == "daily-brief-last-afternoon-v1"
        return {
            "date": "2026-03-02",
            "period": "morning",
            "message": "• Prior morning brief",
        }

    monkeypatch.setattr(daily_brief_flow.Variable, "aget", staticmethod(fake_aget))

    message = await daily_brief_flow._load_previous_day_brief("afternoon", now, logger)
    assert message is None


@pytest.mark.asyncio
async def test_generate_brief_with_dedupe_retries_until_non_repetitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _TestLogger()
    previous = (
        "• <b>📰 News</b>: India inflation cools and Redmond announces Copilot update\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.2% led by Nvidia"
    )
    generated = iter(
        [
            "• <b>📰 News</b>: India inflation cools while Redmond ships Copilot changes\n"
            "• <b>📈 Markets (US)</b>: Nasdaq +1.1% with Nvidia leading gains",
            "• <b>📰 News</b>: India unveils EV policy and Redmond expands AI hiring\n"
            "• <b>📈 Markets (US)</b>: Dow gains as energy stocks advance",
        ]
    )
    calls = {"count": 0}

    async def fake_generate(logger_obj, prompt=None):  # noqa: ANN001
        calls["count"] += 1
        return next(generated)

    monkeypatch.setattr(daily_brief_flow, "_generate_brief", fake_generate)
    monkeypatch.setattr(
        daily_brief_flow,
        "_build_prompt",
        lambda previous_brief=None, rejected_brief=None: "prompt",
    )

    result = await daily_brief_flow._generate_brief_with_dedupe(logger, previous)
    assert "India unveils EV policy" in result
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_generate_brief_with_dedupe_uses_final_attempt_when_still_repetitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _TestLogger()
    previous = (
        "• <b>📰 News</b>: India inflation cools and Redmond announces Copilot update\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.2% led by Nvidia"
    )
    responses = [
        "• <b>📰 News</b>: India inflation cools and Redmond announces Copilot update\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.2% led by Nvidia",
        "• <b>📰 News</b>: India inflation cools while Redmond announces Copilot update\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.2% led by Nvidia",
        "• <b>📰 News</b>: India inflation cools and Redmond Copilot update continues\n"
        "• <b>📈 Markets (US)</b>: Nasdaq +1.1% led by Nvidia",
    ]
    calls = {"count": 0}

    async def fake_generate(logger_obj, prompt=None):  # noqa: ANN001
        idx = calls["count"]
        calls["count"] += 1
        return responses[idx]

    monkeypatch.setattr(daily_brief_flow, "_generate_brief", fake_generate)
    monkeypatch.setattr(
        daily_brief_flow,
        "_build_prompt",
        lambda previous_brief=None, rejected_brief=None: "prompt",
    )

    result = await daily_brief_flow._generate_brief_with_dedupe(logger, previous)
    assert result == responses[-1]
    assert calls["count"] == daily_brief_flow.MAX_REPEAT_RETRIES + 1


@pytest.mark.asyncio
async def test_save_today_brief_persists_only_latest_for_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 3, 3, 7, 0, tzinfo=daily_brief_flow.PACIFIC_TZ)
    logger = _TestLogger()
    captured: dict[str, object] = {}

    async def fake_aset(name: str, value, tags=None, overwrite=False):  # noqa: ANN001
        captured["name"] = name
        captured["value"] = value
        captured["overwrite"] = overwrite
        return None

    monkeypatch.setattr(daily_brief_flow.Variable, "aset", staticmethod(fake_aset))

    await daily_brief_flow._save_today_brief(
        period="morning",
        now=now,
        raw_message="• New message",
        logger=logger,
    )

    assert captured["name"] == "daily-brief-last-morning-v1"
    assert captured["overwrite"] is True
    assert captured["value"] == {
        "date": "2026-03-03",
        "period": "morning",
        "message": "• New message",
    }
