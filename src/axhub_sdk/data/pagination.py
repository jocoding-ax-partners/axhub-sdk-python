"""Offset pagination helpers used by the data layer (subset of node core
pagination.ts that the data ergonomic layer depends on).

Ported: ``serialize_order_by`` / ``normalize_order_by``, ``is_v2_cursor``,
``MAX_CURSOR_TOKEN_LENGTH``, ``list_all``, and the ``PaginatedList`` /
``ListAllItem`` result shapes. Keyset encode/decode is intentionally NOT
ported: the live AX Hub data API is offset-only, so the data layer only needs
the order-by normalizer and the cursor-shape guards used to reject legacy
keyset tokens (see node, gap-matrix S7-S9).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator, Sequence

MAX_CURSOR_TOKEN_LENGTH = 4096


@dataclass
class PaginatedList:
    items: list[Any]
    next_cursor: str | None
    first_cursor: str | None = None
    has_next: bool | None = None
    has_prev: bool | None = None
    total: int | None = None
    total_is_exact: bool | None = None


@dataclass
class ListAllItem:
    """Either an item (``type == "item"``) or a drift marker
    (``type == "drift"``) when the backend total grows mid-scan."""

    type: str
    value: Any = None
    added_since: int = 0


# DataOrderBy = str | Sequence[{"field": str, "dir"?: "asc"|"desc"}]


def normalize_order_by(order_by: Any) -> list[dict[str, str]]:
    if isinstance(order_by, str):
        fields: list[dict[str, str]] = []
        for part in order_by.split(","):
            trimmed = part.strip()
            if trimmed.startswith("-"):
                f = {"field": trimmed[1:], "dir": "desc"}
            elif trimmed.startswith("+"):
                f = {"field": trimmed[1:], "dir": "asc"}
            else:
                f = {"field": trimmed, "dir": "asc"}
            if f["field"]:
                fields.append(f)
    elif order_by:
        fields = [{"field": p["field"], "dir": p.get("dir", "asc")} for p in order_by]
    else:
        fields = []
    if fields and not any(f["field"] == "id" for f in fields):
        fields.append({"field": "id", "dir": "asc"})
    return fields


def serialize_order_by(order_by: Any) -> str | None:
    normalized = normalize_order_by(order_by)
    if not normalized:
        return order_by if isinstance(order_by, str) else None
    return ",".join(f"{'-' if f['dir'] == 'desc' else ''}{f['field']}" for f in normalized)


def is_v2_cursor(token: Any) -> bool:
    return isinstance(token, str) and token.startswith("v2:")


def list_all(
    fetcher: Callable[[dict[str, Any]], PaginatedList],
    opts: dict[str, Any] | None = None,
) -> Iterator[ListAllItem]:
    """Drive a paginated fetcher to exhaustion, yielding each item and a drift
    marker when the backend total grows mid-iteration (mirrors node listAll)."""
    opts = opts or {}
    cursor = opts.get("cursor")
    initial_total: int | None = None
    last_total: int | None = None
    while True:
        page = fetcher({"page_size": opts.get("page_size"), "cursor": cursor})
        if page.total is not None:
            if initial_total is None:
                initial_total = page.total
                last_total = page.total
            elif page.total > (last_total if last_total is not None else initial_total):
                base = last_total if last_total is not None else initial_total
                yield ListAllItem(type="drift", added_since=page.total - base)
                last_total = page.total
        for item in page.items:
            yield ListAllItem(type="item", value=item)
        if page.next_cursor is None:
            return
        cursor = page.next_cursor


__all__ = [
    "MAX_CURSOR_TOKEN_LENGTH",
    "PaginatedList",
    "ListAllItem",
    "normalize_order_by",
    "serialize_order_by",
    "is_v2_cursor",
    "list_all",
]
