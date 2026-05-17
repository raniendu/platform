from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Awaitable, Callable, Literal

from parallel import AsyncParallel
from pydantic_ai import RunContext

from raman.grocery import GroceryListStore
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


async def grocery_list(
    ctx: RunContext[None],
    action: Literal["show", "add", "remove", "mark_bought", "clear"],
    item: str | None = None,
) -> str:
    """Manage this chat's grocery list.

    Use this when the user asks to show, add to, remove from, mark bought on,
    or clear the grocery list. Lists are scoped to the current conversation.

    Args:
        action: The operation to perform: show, add, remove, mark_bought, or clear.
        item: Grocery item name. Required for add, remove, and mark_bought.
    """
    scope = ctx.conversation_id or "default"
    store = GroceryListStore(RamanSettings().grocery_list_path)

    try:
        if action == "show":
            items = store.list_items(scope)
            if not items:
                return "Grocery list is empty for this chat."
            lines = [f"- {entry.item} (added {entry.added_date})" for entry in items]
            return "Grocery list:\n" + "\n".join(lines)

        if action == "add":
            result = store.add_item(
                scope,
                item,
                added_date=datetime.now().astimezone().date().isoformat(),
            )
            if result.created:
                return (
                    f"Added {result.item.item} to this chat's grocery list "
                    f"on {result.item.added_date}."
                )
            return (
                f"{result.item.item} is already on this chat's grocery list "
                f"(added {result.item.added_date})."
            )

        if action == "remove":
            removed = store.remove_item(scope, item)
            if removed is None:
                return f"{item} is not on this chat's grocery list."
            return (
                f"Removed {removed.item} from this chat's grocery list "
                f"(added {removed.added_date})."
            )

        if action == "mark_bought":
            removed = store.remove_item(scope, item)
            if removed is None:
                return f"{item} is not on this chat's grocery list."
            return (
                f"Marked {removed.item} as bought and removed it from this "
                f"chat's grocery list (added {removed.added_date})."
            )

        if action == "clear":
            count = store.clear(scope)
            if count == 0:
                return "Grocery list is already empty for this chat."
            noun = "item" if count == 1 else "items"
            return f"Cleared {count} {noun} from this chat's grocery list."
    except ValueError as exc:
        if (
            action in {"add", "remove", "mark_bought"}
            and str(exc) == "item is required"
        ):
            return f"Grocery list error: item is required for {action}."
        return f"Grocery list error: {exc}"

    return f"Grocery list error: unsupported action {action!r}."


TOOL_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "web_search": web_search,
    "grocery_list": grocery_list,
}
