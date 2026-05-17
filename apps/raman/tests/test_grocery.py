from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from raman.grocery import GroceryListStore
from raman.tools import grocery_list

FROZEN_DATE = "2026-05-17"


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 5, 17, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def freeze_tool_date(monkeypatch):
    monkeypatch.setattr("raman.tools.datetime", FrozenDateTime)


def _ctx(conversation_id: str) -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conversation_id)


@pytest.mark.asyncio
async def test_grocery_tool_adds_and_shows_items_with_added_date(monkeypatch, tmp_path):
    monkeypatch.setenv("RAMAN_GROCERY_LIST_PATH", str(tmp_path / "grocery.json"))
    ctx = _ctx("telegram:gobind:123")

    added = await grocery_list(ctx, action="add", item="Milk")
    shown = await grocery_list(ctx, action="show")

    assert added == f"Added Milk to this chat's grocery list on {FROZEN_DATE}."
    assert shown == f"Grocery list:\n- Milk (added {FROZEN_DATE})"


@pytest.mark.asyncio
async def test_grocery_tool_does_not_duplicate_case_insensitive_items(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RAMAN_GROCERY_LIST_PATH", str(tmp_path / "grocery.json"))
    ctx = _ctx("telegram:gobind:123")

    await grocery_list(ctx, action="add", item="Milk")
    duplicate = await grocery_list(ctx, action="add", item="  milk  ")
    shown = await grocery_list(ctx, action="show")

    assert duplicate == (
        f"Milk is already on this chat's grocery list (added {FROZEN_DATE})."
    )
    assert shown.count("Milk") == 1


@pytest.mark.asyncio
async def test_grocery_tool_removes_and_marks_bought_by_normalized_match(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RAMAN_GROCERY_LIST_PATH", str(tmp_path / "grocery.json"))
    ctx = _ctx("telegram:gobind:123")

    await grocery_list(ctx, action="add", item="Milk")
    removed = await grocery_list(ctx, action="remove", item=" milk ")
    after_remove = await grocery_list(ctx, action="show")
    await grocery_list(ctx, action="add", item="Eggs")
    bought = await grocery_list(ctx, action="mark_bought", item="EGGS")
    after_bought = await grocery_list(ctx, action="show")

    assert removed == (
        f"Removed Milk from this chat's grocery list (added {FROZEN_DATE})."
    )
    assert after_remove == "Grocery list is empty for this chat."
    assert bought == (
        f"Marked Eggs as bought and removed it from this chat's grocery list "
        f"(added {FROZEN_DATE})."
    )
    assert after_bought == "Grocery list is empty for this chat."


@pytest.mark.asyncio
async def test_grocery_tool_clears_only_current_conversation(monkeypatch, tmp_path):
    monkeypatch.setenv("RAMAN_GROCERY_LIST_PATH", str(tmp_path / "grocery.json"))
    first = _ctx("telegram:gobind:123")
    second = _ctx("telegram:gobind:456")

    await grocery_list(first, action="add", item="Milk")
    await grocery_list(second, action="add", item="Apples")
    cleared = await grocery_list(first, action="clear")
    first_shown = await grocery_list(first, action="show")
    second_shown = await grocery_list(second, action="show")

    assert cleared == "Cleared 1 item from this chat's grocery list."
    assert first_shown == "Grocery list is empty for this chat."
    assert second_shown == f"Grocery list:\n- Apples (added {FROZEN_DATE})"


@pytest.mark.asyncio
async def test_grocery_tool_returns_clear_errors_for_missing_items(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RAMAN_GROCERY_LIST_PATH", str(tmp_path / "grocery.json"))
    ctx = _ctx("telegram:gobind:123")

    add_error = await grocery_list(ctx, action="add", item="  ")
    remove_error = await grocery_list(ctx, action="remove", item=None)
    bought_error = await grocery_list(ctx, action="mark_bought", item=None)

    assert add_error == "Grocery list error: item is required for add."
    assert remove_error == "Grocery list error: item is required for remove."
    assert bought_error == "Grocery list error: item is required for mark_bought."


def test_grocery_store_reports_malformed_files(tmp_path):
    path = tmp_path / "grocery.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        GroceryListStore(path).list_items("telegram:gobind:123")
