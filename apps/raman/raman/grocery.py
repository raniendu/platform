from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GroceryItem:
    item: str
    added_date: str


@dataclass(frozen=True)
class GroceryAddResult:
    item: GroceryItem
    created: bool


class GroceryListStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def list_items(self, scope: str) -> list[GroceryItem]:
        data = self._load()
        return [
            GroceryItem(item=str(entry["item"]), added_date=str(entry["added_date"]))
            for entry in self._lists(data).get(scope, [])
        ]

    def add_item(
        self, scope: str, item: str | None, *, added_date: str
    ) -> GroceryAddResult:
        display_item = clean_item(item)
        data = self._load()
        items = self._lists(data).setdefault(scope, [])
        normalized = normalize_item(display_item)

        for entry in items:
            if normalize_item(str(entry["item"])) == normalized:
                return GroceryAddResult(
                    GroceryItem(
                        item=str(entry["item"]),
                        added_date=str(entry["added_date"]),
                    ),
                    created=False,
                )

        entry = {"item": display_item, "added_date": added_date}
        items.append(entry)
        self._save(data)
        return GroceryAddResult(
            GroceryItem(item=display_item, added_date=added_date),
            created=True,
        )

    def remove_item(self, scope: str, item: str | None) -> GroceryItem | None:
        display_item = clean_item(item)
        data = self._load()
        lists = self._lists(data)
        items = lists.get(scope, [])
        normalized = normalize_item(display_item)

        for index, entry in enumerate(items):
            if normalize_item(str(entry["item"])) == normalized:
                removed = items.pop(index)
                if not items:
                    lists.pop(scope, None)
                self._save(data)
                return GroceryItem(
                    item=str(removed["item"]),
                    added_date=str(removed["added_date"]),
                )
        return None

    def clear(self, scope: str) -> int:
        data = self._load()
        lists = self._lists(data)
        items = lists.pop(scope, [])
        count = len(items)
        if count:
            self._save(data)
        return count

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": SCHEMA_VERSION, "lists": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Grocery list file {self.path} is not valid JSON."
            ) from exc
        self._validate(data)
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        tmp_path.write_text(
            f"{json.dumps(data, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def _lists(self, data: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        return data["lists"]

    def _validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            raise ValueError(f"Grocery list file {self.path} must contain an object.")
        if data.get("version") != SCHEMA_VERSION:
            raise ValueError(
                f"Grocery list file {self.path} has an unsupported schema version."
            )
        lists = data.get("lists")
        if not isinstance(lists, dict):
            raise ValueError(
                f"Grocery list file {self.path} must contain a lists object."
            )
        for scope, items in lists.items():
            if not isinstance(scope, str) or not isinstance(items, list):
                raise ValueError(
                    f"Grocery list file {self.path} has an invalid list entry."
                )
            for entry in items:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("item"), str)
                    or not isinstance(entry.get("added_date"), str)
                ):
                    raise ValueError(
                        f"Grocery list file {self.path} has an invalid item entry."
                    )


def clean_item(item: str | None) -> str:
    if item is None:
        raise ValueError("item is required")
    display_item = " ".join(item.split())
    if not display_item:
        raise ValueError("item is required")
    return display_item


def normalize_item(item: str) -> str:
    return " ".join(item.casefold().split())
