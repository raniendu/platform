from __future__ import annotations

from functools import lru_cache
from typing import Awaitable, Callable

from parallel import AsyncParallel

from raman.settings import RamanSettings


@lru_cache(maxsize=1)
def _parallel_client() -> AsyncParallel:
    settings = RamanSettings()
    if not settings.parallel_api_key:
        raise RuntimeError(
            "PARALLEL_API_KEY is not set. Add it to .env to enable web_search."
        )
    return AsyncParallel(api_key=settings.parallel_api_key)


async def web_search(query: str) -> str:
    """Search the public web for current or factual information.

    Use this when the answer depends on information you do not already know,
    such as recent events, prices, dates, documentation, or anything that may
    have changed.

    Args:
        query: A concise natural-language search query, ideally 3-10 words.
    """
    response = await _parallel_client().search(
        search_queries=[query],
        objective=query,
        mode="basic",
    )
    if not response.results:
        return f"No results for: {query}"

    blocks: list[str] = []
    for r in response.results[:5]:
        title = r.title or r.url
        excerpt = "\n".join(r.excerpts) if r.excerpts else ""
        blocks.append(f"## {title}\n{r.url}\n\n{excerpt}".rstrip())
    return "\n\n---\n\n".join(blocks)


TOOL_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "web_search": web_search,
}
