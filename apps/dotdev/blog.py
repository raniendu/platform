"""Utilities for loading and structuring markdown blog posts."""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

try:  # pragma: no cover - prefer real library when available
    import frontmatter
except ModuleNotFoundError:  # pragma: no cover - fallback parser for tests

    @dataclass
    class _FrontMatterDocument:
        metadata: Dict[str, Any]
        content: str

    def _parse_metadata(lines: Sequence[str]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        current_key: Optional[str] = None
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("- ") and current_key:
                metadata.setdefault(current_key, []).append(line[2:].strip())
                continue
            if line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value:
                    metadata[key] = value
                else:
                    metadata[key] = []
                current_key = key
        return metadata

    def load(path: Union[Path, str]) -> _FrontMatterDocument:
        text = Path(path).read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return _FrontMatterDocument({}, text)

        metadata_lines: List[str] = []
        content_start = len(lines)
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                content_start = index + 1
                break
            metadata_lines.append(lines[index])

        metadata = _parse_metadata(metadata_lines)
        content = "\n".join(lines[content_start:])
        return _FrontMatterDocument(metadata, content)

    frontmatter = type("_FrontMatterModule", (), {"load": staticmethod(load)})()


try:  # pragma: no cover - prefer real markdown implementation
    import markdown
except ModuleNotFoundError:  # pragma: no cover - fallback renderer for tests

    class _MarkdownModule:
        @staticmethod
        def markdown(text: str, extensions: Optional[Sequence[str]] = None) -> str:
            paragraphs = [line.strip() for line in text.split("\n\n") if line.strip()]
            return "\n".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)

    markdown = _MarkdownModule()

POSTS_DIR = Path(__file__).resolve().parent / "posts"

# Basic English stop words for word cloud generation. Keeps dependencies light.
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
    "was",
    "will",
    "with",
}


@dataclass()
class Post:
    """Represents a blog post loaded from Markdown with metadata."""

    slug: str
    title: str
    date: _dt.datetime
    tags: Sequence[str]
    content_html: str
    excerpt: str
    word_bank: Sequence[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "date": self.date.date().isoformat(),
            "displayDate": self.date.strftime("%B %d, %Y"),
            "tags": list(self.tags),
            "content": self.content_html,
            "excerpt": self.excerpt,
        }


def load_posts(posts_dir: Optional[Path] = None) -> List[Post]:
    """Load, parse, and sort posts from the posts directory."""
    directory = posts_dir or POSTS_DIR
    if not directory.exists():
        return []

    posts: List[Post] = []
    for path in sorted(directory.glob("*.md")):
        try:
            posts.append(_parse_post(path))
        except Exception as exc:  # pragma: no cover - defensive logging hook
            print(f"Failed to parse post {path.name}: {exc}")
            continue

    posts.sort(key=lambda post: post.date, reverse=True)
    return posts


def build_archive_index(posts: Sequence[Post]) -> List[Dict[str, Any]]:
    """Return posts grouped by year and month for archive navigation."""
    archive: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for post in posts:
        year_bucket = archive.setdefault(post.date.year, {})
        month_bucket = year_bucket.setdefault(
            post.date.month,
            {
                "month": post.date.strftime("%B"),
                "posts": [],
            },
        )
        month_bucket["posts"].append(
            {
                "slug": post.slug,
                "title": post.title,
                "date": post.date.date().isoformat(),
            }
        )

    structured_index: List[Dict[str, Any]] = []
    for year in sorted(archive.keys(), reverse=True):
        months = archive[year]
        month_entries = []
        for month in sorted(months.keys(), reverse=True):
            month_data = months[month]
            # Ensure posts ordered newest first inside month bucket
            month_data["posts"].sort(key=lambda item: item["date"], reverse=True)
            month_entries.append(
                {
                    "month": month_data["month"],
                    "monthNumber": month,
                    "posts": month_data["posts"],
                }
            )

        structured_index.append({"year": year, "months": month_entries})

    return structured_index


def build_word_cloud(
    posts: Sequence[Post], max_words: int = 10
) -> List[Dict[str, Any]]:
    """Generate a simple word cloud dataset from the collection of posts."""
    frequencies: Dict[str, int] = {}
    for post in posts:
        for word in post.word_bank:
            frequencies[word] = frequencies.get(word, 0) + 1

    sorted_words = sorted(frequencies.items(), key=lambda item: item[1], reverse=True)
    top_words = sorted_words[:max_words]
    return [{"text": word, "weight": count} for word, count in top_words]


def load_posts_bundle(posts_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Convenience wrapper returning posts, archive index, and word cloud."""
    posts = load_posts(posts_dir=posts_dir)
    return {
        "posts": [post.to_dict() for post in posts],
        "archive": build_archive_index(posts),
        "wordCloud": build_word_cloud(posts),
    }


def _parse_post(path: Path) -> Post:
    """Parse a single markdown file into a Post object."""
    raw = frontmatter.load(path)
    metadata = raw.metadata
    title = str(metadata.get("title") or path.stem.replace("-", " ").title())
    slug = _slugify(metadata.get("slug") or title)

    date = _coerce_date(metadata.get("date"), fallback=_file_datetime(path))
    tags = _coerce_tags(metadata.get("tags"))

    html = markdown.markdown(
        raw.content,
        extensions=[
            "fenced_code",
            "codehilite",
            "tables",
            "sane_lists",
            "toc",
        ],
    )

    excerpt = _make_excerpt(raw.content)
    word_bank = list(_extract_words(raw.content, tags))

    return Post(
        slug=slug,
        title=title,
        date=date,
        tags=tags,
        content_html=html,
        excerpt=excerpt,
        word_bank=word_bank,
    )


def _make_excerpt(content: str, limit: int = 40) -> str:
    """Create a short excerpt from the markdown content."""
    words = content.strip().split()
    snippet = " ".join(words[:limit])
    if len(words) > limit:
        snippet += "..."
    return snippet


def _file_datetime(path: Path) -> _dt.datetime:
    return _dt.datetime.fromtimestamp(path.stat().st_mtime)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"post-{int(_dt.datetime.now().timestamp())}"


def _coerce_date(value: Any, fallback: _dt.datetime) -> _dt.datetime:
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime.combine(value, _dt.time.min)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return _dt.datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            # Attempt ISO parsing allowing timezone offset.
            return _dt.datetime.fromisoformat(value)
        except ValueError:
            pass
    return fallback


def _coerce_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # Support comma-separated strings
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, Iterable):
        items = [str(item).strip() for item in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def _extract_words(content: str, tags: Sequence[str]) -> Iterable[str]:
    """Extract lowercase words while excluding stop words and short tokens."""
    words = re.findall(r"[a-zA-Z]{3,}", content.lower())
    for word in words:
        if word not in _STOP_WORDS:
            yield word
    for tag in tags:
        tag_words = re.findall(r"[a-zA-Z]{3,}", tag.lower())
        for tag_word in tag_words:
            if tag_word not in _STOP_WORDS:
                yield tag_word


# Allow CLI usage for debugging
if __name__ == "__main__":  # pragma: no cover - convenience helper
    bundle = load_posts_bundle()
    print(json.dumps(bundle, indent=2))
