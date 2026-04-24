"""Behavior tests for daily brief verification and rendering logic."""

from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("prefect", reason="prefect is required to import flow module")

from flows.daily_brief import (
    NewsCandidate,
    _resolve_period,
    _verify_candidate,
    render_brief,
    verify_news_candidates,
)


def _valid_candidate(**overrides) -> NewsCandidate:
    payload = {
        "headline": "Contoso opens new AI lab in Redmond",
        "summary": "Contoso opened a new AI lab in Redmond and announced hiring plans.",
        "source_url": "https://example.com/news/contoso-ai-lab",
        "publisher_name": "Example News",
        "published_timestamp": datetime(2026, 1, 5, 12, 0, 0),
        "evidence_snippet": (
            "Contoso opened a new AI lab in Redmond on Monday. "
            "The company said the lab will focus on applied AI and is hiring engineers."
        ),
    }
    payload.update(overrides)
    return NewsCandidate(**payload)


def test_resolve_period_accepts_valid_overrides() -> None:
    assert _resolve_period("Morning") == "Morning"
    assert _resolve_period("Afternoon") == "Afternoon"


def test_resolve_period_rejects_invalid_override() -> None:
    with pytest.raises(ValueError, match="period_override must be one of"):
        _resolve_period("Evening")


def test_candidate_missing_url_gets_rejected() -> None:
    result = _verify_candidate(_valid_candidate(source_url=None))
    assert result.verification_status == "rejected"
    assert result.rejection_reason == "missing_or_invalid_source_url"


def test_candidate_missing_publisher_gets_rejected() -> None:
    result = _verify_candidate(_valid_candidate(publisher_name=None))
    assert result.verification_status == "rejected"
    assert result.rejection_reason == "missing_publisher_name"


def test_candidate_missing_timestamp_gets_rejected() -> None:
    result = _verify_candidate(_valid_candidate(published_timestamp=None))
    assert result.verification_status == "rejected"
    assert result.rejection_reason == "missing_published_timestamp"


def test_candidate_missing_evidence_gets_rejected() -> None:
    result = _verify_candidate(_valid_candidate(evidence_snippet=None))
    assert result.verification_status == "rejected"
    assert result.rejection_reason == "missing_evidence_snippet"


def test_candidate_with_unsupported_claim_gets_rejected() -> None:
    result = _verify_candidate(
        _valid_candidate(
            headline="Contoso acquires Fabrikam in a $5B cash deal.",
            summary="Contoso acquires Fabrikam in a $5B cash deal.",
            evidence_snippet="Some random company expanded its engineering office and hired 50 people.",
        )
    )
    assert result.verification_status == "rejected"
    assert result.rejection_reason == "evidence_does_not_support_claim"


def test_verified_candidate_appears_in_final_brief() -> None:
    verified, rejected = verify_news_candidates([_valid_candidate()])
    assert len(verified) == 1
    assert len(rejected) == 0

    message = render_brief("Morning", verified, [])
    assert "Contoso opens new AI lab in Redmond" in message
    assert "No verified updates available" not in message


def test_rejected_candidate_not_in_final_brief() -> None:
    verified, rejected = verify_news_candidates([_valid_candidate(source_url=None)])
    assert len(verified) == 0
    assert len(rejected) == 1

    message = render_brief("Morning", verified, [])
    assert "Contoso opens new AI lab in Redmond" not in message
    assert "No verified updates available." in message


def test_zero_verified_items_renders_safe_fallback() -> None:
    message = render_brief("Afternoon", [], [])
    assert "No verified updates available." in message
    assert "No verified market updates available." in message


def test_duplicate_candidates_are_rejected() -> None:
    candidate = _valid_candidate()
    verified, rejected = verify_news_candidates([candidate, candidate])
    assert len(verified) == 1
    assert len(rejected) == 1
    assert rejected[0].rejection_reason == "duplicate_story"


def test_market_section_uses_structured_data_without_fabrication() -> None:
    message = render_brief("Morning", [_verify_candidate(_valid_candidate())], [])
    assert "No verified market updates available." in message
