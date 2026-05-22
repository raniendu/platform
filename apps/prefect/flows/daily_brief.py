"""Daily brief flow that sends verified notifications via Pushover.

Pipeline summary:
- Fetch source-backed candidate items from external feeds
- Verify each candidate against required metadata/evidence rules
- Render only verified content (with safe fallbacks)
- Optionally rewrite the rendered brief for readability without adding facts
"""

from __future__ import annotations

import html
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl

from prefect import flow, get_run_logger
from prefect.blocks.system import Secret

# Load .env for local development
load_dotenv()

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_APP_TOKEN_BLOCK = "pushover-app-token"
PUSHOVER_USER_KEY_BLOCK = "pushover-user-key"
GEMINI_MODEL = "gemini-3-flash-preview"

_HTML_TAG_RE = re.compile(r"(<\s*/?\s*(?:b|i|u|br)\s*/?>)", re.IGNORECASE)
_STRONG_TAG_RE = re.compile(r"<\s*(/?)\s*strong\s*>", re.IGNORECASE)
_EM_TAG_RE = re.compile(r"<\s*(/?)\s*em\s*>", re.IGNORECASE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)")
_MD_BULLET_RE = re.compile(r"^(\s*)[*-]\s+(.*)$")
_SPECULATIVE_RE = re.compile(
    r"\b(might|may|could|rumou?r|reportedly|unconfirmed|expected to)\b", re.IGNORECASE
)
_WORD_RE = re.compile(r"[a-zA-Z0-9]{4,}")


class NewsCandidate(BaseModel):
    headline: str
    summary: str
    source_url: str | None = None
    publisher_name: str | None = None
    published_timestamp: datetime | None = None
    evidence_snippet: str | None = None


class NewsVerificationResult(BaseModel):
    headline: str
    summary: str
    source_url: str | None = None
    publisher_name: str | None = None
    published_timestamp: datetime | None = None
    evidence_snippet: str | None = None
    verification_status: Literal["verified", "rejected"]
    rejection_reason: str | None = None


class VerifiedNewsItem(BaseModel):
    headline: str
    summary: str
    source_url: HttpUrl
    publisher_name: str
    published_timestamp: datetime
    evidence_snippet: str
    verification_status: Literal["verified"]
    rejection_reason: None = None


class MarketSnapshot(BaseModel):
    name: str
    symbol: str
    current_value: float
    change_percent: float
    as_of: datetime
    source_url: HttpUrl
    verification_status: Literal["verified"] = "verified"


def _is_production() -> bool:
    """Check if running in production (matches config.settings.detect_environment logic)."""
    env_value = os.getenv("ENVIRONMENT") or os.getenv("PREFECT_ENVIRONMENT") or ""
    return env_value.lower() in ("production", "prod")


def _get_pst_now() -> datetime:
    """Get current time in Pacific timezone (PST/PDT)."""
    return datetime.now(PACIFIC_TZ)


def _normalize_html_tags(message: str) -> str:
    """Normalize common HTML tags to ones supported by Pushover."""
    message = _STRONG_TAG_RE.sub(
        lambda match: f"<{'/' if match.group(1) else ''}b>", message
    )
    message = _EM_TAG_RE.sub(
        lambda match: f"<{'/' if match.group(1) else ''}i>", message
    )
    return message


def _sanitize_html(message: str) -> str:
    """Escape HTML while preserving supported tags."""
    parts = _HTML_TAG_RE.split(message)
    sanitized_parts: list[str] = []
    for part in parts:
        if _HTML_TAG_RE.fullmatch(part):
            sanitized_parts.append(part)
        else:
            sanitized_parts.append(html.escape(part))
    return "".join(sanitized_parts)


def _convert_markdown_to_html(message: str) -> str:
    """Convert lightweight Markdown used by summaries into supported Pushover HTML."""
    converted_lines: list[str] = []
    for line in message.splitlines():
        bullet_match = _MD_BULLET_RE.match(line)
        if bullet_match:
            indent, body = bullet_match.groups()
            line = f"{indent}• {body}"
        converted_lines.append(line)

    converted = "\n".join(converted_lines)
    converted = _MD_BOLD_RE.sub(r"<b>\1</b>", converted)
    converted = _MD_ITALIC_RE.sub(r"<i>\1</i>", converted)
    return converted


def _format_pushover_message(message: str) -> tuple[str, int]:
    """Return a message and html flag based on detected formatting."""
    message = message.strip()
    if not message:
        return message, 0

    # Gemini may return Markdown; convert common Markdown formatting so Pushover
    # can render the final notification as rich text.
    message = _convert_markdown_to_html(message)

    # Normalize common HTML tags first (e.g. <strong> -> <b>).
    message = _normalize_html_tags(message)

    # No tag-like content at all: send plain text without HTML mode.
    if "<" not in message and ">" not in message:
        return message, 0

    # Always sanitize when tag-like content is present; only enable HTML mode
    # if supported tags remain after normalization.
    has_html = bool(_HTML_TAG_RE.search(message))
    sanitized = _sanitize_html(message)
    return sanitized, 1 if has_html else 0


def _resolve_period(period_override: str | None) -> str:
    """Resolve briefing period from override or current Pacific time."""
    if period_override is None:
        return "Morning" if _get_pst_now().hour < 12 else "Afternoon"
    if period_override in {"Morning", "Afternoon"}:
        return period_override
    raise ValueError("period_override must be one of: 'Morning', 'Afternoon', or None")


def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw).strip()


def _is_valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _find_tokens(text: str) -> set[str]:
    return {token.lower() for token in _WORD_RE.findall(text)}


def _evidence_supports_claim(
    headline: str, summary: str, evidence_snippet: str
) -> bool:
    evidence_tokens = _find_tokens(evidence_snippet)
    if len(evidence_tokens) < 4:
        return False
    headline_tokens = _find_tokens(headline)
    summary_tokens = _find_tokens(summary)
    return bool(headline_tokens & evidence_tokens) and bool(
        summary_tokens & evidence_tokens
    )


def _verify_candidate(candidate: NewsCandidate) -> NewsVerificationResult:
    reason: str | None = None

    if not _is_valid_http_url(candidate.source_url):
        reason = "missing_or_invalid_source_url"
    elif not candidate.publisher_name:
        reason = "missing_publisher_name"
    elif not candidate.published_timestamp:
        reason = "missing_published_timestamp"
    elif not candidate.evidence_snippet:
        reason = "missing_evidence_snippet"
    elif len(candidate.evidence_snippet.split()) < 8:
        reason = "evidence_too_vague"
    elif _SPECULATIVE_RE.search(f"{candidate.headline} {candidate.summary}"):
        reason = "speculative_or_embellished_claim"
    elif not _evidence_supports_claim(
        candidate.headline,
        candidate.summary,
        candidate.evidence_snippet,
    ):
        reason = "evidence_does_not_support_claim"

    if reason:
        return NewsVerificationResult(
            headline=candidate.headline,
            summary=candidate.summary,
            source_url=candidate.source_url,
            publisher_name=candidate.publisher_name,
            published_timestamp=candidate.published_timestamp,
            evidence_snippet=candidate.evidence_snippet,
            verification_status="rejected",
            rejection_reason=reason,
        )

    return NewsVerificationResult(
        headline=candidate.headline,
        summary=candidate.summary,
        source_url=candidate.source_url,
        publisher_name=candidate.publisher_name,
        published_timestamp=candidate.published_timestamp,
        evidence_snippet=candidate.evidence_snippet,
        verification_status="verified",
        rejection_reason=None,
    )


def verify_news_candidates(
    candidates: list[NewsCandidate],
) -> tuple[list[VerifiedNewsItem], list[NewsVerificationResult]]:
    verified: list[VerifiedNewsItem] = []
    rejected: list[NewsVerificationResult] = []
    seen_keys: set[str] = set()

    for candidate in candidates:
        verification = _verify_candidate(candidate)
        dedupe_key = (
            f"{candidate.source_url or ''}|{candidate.headline.lower().strip()}"
        )

        if verification.verification_status == "verified" and dedupe_key in seen_keys:
            verification = verification.model_copy(
                update={
                    "verification_status": "rejected",
                    "rejection_reason": "duplicate_story",
                }
            )

        if verification.verification_status == "verified":
            required_fields_present = all(
                [
                    verification.source_url,
                    verification.publisher_name,
                    verification.published_timestamp,
                    verification.evidence_snippet,
                ]
            )
            if not required_fields_present:
                rejected.append(
                    verification.model_copy(
                        update={
                            "verification_status": "rejected",
                            "rejection_reason": "internal_verification_invariant_failed",
                        }
                    )
                )
                continue

            seen_keys.add(dedupe_key)
            verified.append(
                VerifiedNewsItem(
                    headline=verification.headline,
                    summary=verification.summary,
                    source_url=verification.source_url,
                    publisher_name=verification.publisher_name,
                    published_timestamp=verification.published_timestamp,
                    evidence_snippet=verification.evidence_snippet,
                    verification_status="verified",
                    rejection_reason=None,
                )
            )
        else:
            rejected.append(verification)

    return verified, rejected


def render_brief(
    period: str,
    verified_news: list[VerifiedNewsItem],
    market_data: list[MarketSnapshot],
) -> str:
    now = _get_pst_now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p")

    lines = [
        f"<b>📅 {date_str}</b>",
        f"<b>🕐 {period} Brief ({time_str})</b>",
        "",
        "• <b>📰 News</b>",
    ]

    if verified_news:
        for item in verified_news[:2]:
            lines.append(
                f"  - <b>{item.headline}</b> ({item.publisher_name}) "
                f"<i>{item.summary}</i> [source: {item.source_url}]"
            )
    else:
        lines.append("  - No verified updates available.")

    lines.append("• <b>📈 Markets</b>")
    if market_data:
        for quote in market_data:
            lines.append(
                f"  - {quote.name}: {quote.current_value:.2f} ({quote.change_percent:+.2f}%) [source: {quote.source_url}]"
            )
    else:
        lines.append("  - No verified market updates available.")

    lines.append(
        "• <b>💡 Inspiration</b>: Keep inputs factual and decisions deliberate."
    )
    return "\n".join(lines)


async def _fetch_google_news_candidates(
    query: str, limit: int = 5
) -> list[NewsCandidate]:
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(rss_url)
        response.raise_for_status()

    root = ET.fromstring(response.text)
    items = root.findall("./channel/item")
    candidates: list[NewsCandidate] = []

    for item in items[:limit]:
        headline = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        description = _strip_html(item.findtext("description", default=""))
        source = item.find("source")
        publisher_name = (
            source.text.strip() if source is not None and source.text else None
        )

        published_timestamp = None
        if pub_date:
            try:
                published_timestamp = parsedate_to_datetime(pub_date)
            except Exception:
                published_timestamp = None

        summary = description[:220] if description else headline
        candidates.append(
            NewsCandidate(
                headline=headline,
                summary=summary,
                source_url=link or None,
                publisher_name=publisher_name,
                published_timestamp=published_timestamp,
                evidence_snippet=description[:320] if description else None,
            )
        )

    return candidates


async def _fetch_market_snapshots(period: str, logger) -> list[MarketSnapshot]:
    symbols = [
        ("S&P 500", "^GSPC"),
        ("Nasdaq", "^IXIC"),
    ]
    if period == "Morning":
        symbols = [("Nifty 50", "^NSEI"), ("Sensex", "^BSESN")]

    quotes: list[MarketSnapshot] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for name, symbol in symbols:
            url_symbol = symbol.replace("^", "%5E")
            source_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{url_symbol}?range=2d&interval=1d"
            try:
                response = await client.get(source_url)
                response.raise_for_status()
                payload = response.json()
                result = payload["chart"]["result"][0]
                closes = [
                    v
                    for v in result["indicators"]["quote"][0]["close"]
                    if v is not None
                ]
                timestamps = result["timestamp"]
                if len(closes) < 2:
                    continue
                current = float(closes[-1])
                prev = float(closes[-2])
                change_pct = ((current - prev) / prev) * 100
                as_of = datetime.fromtimestamp(int(timestamps[-1]), tz=PACIFIC_TZ)
                quotes.append(
                    MarketSnapshot(
                        name=name,
                        symbol=symbol,
                        current_value=current,
                        change_percent=change_pct,
                        as_of=as_of,
                        source_url=source_url,
                    )
                )
            except Exception as exc:
                logger.warning(f"Market fetch failed for {symbol}: {exc}")

    return quotes


async def _summarize_verified_brief(logger, period: str, rendered_brief: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return rendered_brief

    try:
        from google import genai
    except ImportError:
        return rendered_brief

    prompt = (
        "Rewrite the briefing for readability using ONLY the provided verified facts. "
        "Do not add new facts, numbers, locations, dates, or attributions. "
        "Preserve uncertainty exactly as stated. If data is missing, keep fallback text unchanged.\n\n"
        f"Period: {period}\n"
        f"Verified briefing facts:\n{rendered_brief}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL, contents=prompt
        )
        content = response.text.strip() if response.text else ""
        return content or rendered_brief
    except Exception as exc:
        logger.warning(
            f"Gemini summarization failed; using deterministic rendering: {exc}"
        )
        return rendered_brief


async def _load_secret_block_value(block_name: str) -> str | None:
    try:
        block = await Secret.aload(block_name)
        value = str(block.get()).strip()
        return value or None
    except Exception:
        return None


async def _load_pushover_credentials() -> tuple[str, str]:
    app_token = await _load_secret_block_value(PUSHOVER_APP_TOKEN_BLOCK)
    user_key = await _load_secret_block_value(PUSHOVER_USER_KEY_BLOCK)

    app_token = app_token or os.getenv("PUSHOVER_APP_TOKEN", "").strip()
    user_key = user_key or os.getenv("PUSHOVER_USER_KEY", "").strip()

    if not app_token or not user_key:
        raise RuntimeError(
            "Pushover credentials must be available as Prefect Secret blocks "
            "or PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY environment variables"
        )

    return app_token, user_key


@flow(name="daily-brief", retries=1, retry_delay_seconds=300)
async def daily_brief(period_override: str | None = None) -> None:
    logger = get_run_logger()

    app_token, user_key = await _load_pushover_credentials()

    title_prefix = "" if _is_production() else "[Dev] "
    title = f"{title_prefix}📋 Daily Brief"
    period = _resolve_period(period_override)

    regional_queries = ["India top headlines", "Redmond WA technology"]
    candidates: list[NewsCandidate] = []
    for query in regional_queries:
        try:
            candidates.extend(await _fetch_google_news_candidates(query, limit=4))
        except Exception as exc:
            logger.warning(f"News fetch failed for query '{query}': {exc}")

    verified_news, rejected_news = verify_news_candidates(candidates)
    market_data = await _fetch_market_snapshots(period, logger)

    logger.info(
        "News verification completed: candidates=%d verified=%d rejected=%d reasons=%s",
        len(candidates),
        len(verified_news),
        len(rejected_news),
        {
            reason: sum(1 for i in rejected_news if i.rejection_reason == reason)
            for reason in {i.rejection_reason for i in rejected_news}
        },
    )
    logger.info("Market snapshots rendered=%d", len(market_data))

    deterministic_message = render_brief(period, verified_news, market_data)
    raw_message = await _summarize_verified_brief(logger, period, deterministic_message)
    message, html_flag = _format_pushover_message(raw_message)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            PUSHOVER_API_URL,
            data={
                "token": app_token,
                "user": user_key,
                "title": title,
                "message": message,
                "html": html_flag,
            },
        )

    if response.status_code == 200:
        logger.info("Pushover notification sent successfully")
    else:
        raise RuntimeError(
            f"Pushover notification failed: {response.status_code} — {response.text}"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(daily_brief())
