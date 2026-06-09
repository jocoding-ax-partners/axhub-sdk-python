"""Predicate DSL: ``where(col).eq(v)``, ``and_(...)``, ``or_``/``not_``/``raw``
plus LIKE escaping and ReDoS guards (mirrors node dsl/ops.ts).

Query expressions are plain dicts:
  {"op": "eq"|"ne"|"gt"|"gte"|"lt"|"lte"|"like", "column": str, "value": Any}
  {"op": "in", "column": str, "values": [...]}
  {"op": "and"|"or", "clauses": [...]}
  {"op": "not", "clause": expr}
  {"op": "raw", "sql": str, "params"?: [...]}
Only ``and(eq/ne/gt/gte/lt/lte/in/like)`` and bare atoms are pushable to the
live backend; or/not/raw raise in the where-serializer (mirrors node).
"""
from __future__ import annotations

import re
from typing import Any

from .schema import DataColumn
from ..errors import ValidationError

MAX_LIKE_PATTERN_LENGTH = 1024
MAX_CONSECUTIVE_WILDCARDS = 4
MAX_LIKE_ALTERNATION_SEGMENTS = 6

_ESCAPE_LIKE_RE = re.compile(r"[\\%_]")


def escape_like(value: str) -> str:
    if value == "":
        return value
    return _ESCAPE_LIKE_RE.sub(lambda m: "\\" + m.group(0), value)


def assert_safe_like_pattern(pattern: str) -> None:
    """Reject LIKE patterns that translate to catastrophic-backtracking regex
    shapes (mirrors node assertSafeLikePattern)."""
    if len(pattern) > MAX_LIKE_PATTERN_LENGTH:
        raise ValidationError(
            f"LIKE pattern exceeds {MAX_LIKE_PATTERN_LENGTH} chars; refuse to compile",
            "like_pattern_too_long",
        )
    run_of_wildcards = 0
    segments = 0
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            run_of_wildcards = 0
            continue
        if ch == "%":
            run_of_wildcards += 1
            if run_of_wildcards >= MAX_CONSECUTIVE_WILDCARDS:
                raise ValidationError(
                    f"LIKE pattern has {run_of_wildcards} consecutive '%'; refuse to compile (ReDoS guard)",
                    "like_pattern_redos",
                )
        else:
            if run_of_wildcards == 1:
                segments += 1
            run_of_wildcards = 0
        i += 1
    if segments > MAX_LIKE_ALTERNATION_SEGMENTS:
        raise ValidationError(
            f"LIKE pattern has {segments} '%X%' alternation segments; refuse to compile (ReDoS guard)",
            "like_pattern_redos",
        )


def raw(sql: str, params: list[Any] | None = None) -> dict[str, Any]:
    return {"op": "raw", "sql": sql, "params": params} if params is not None else {"op": "raw", "sql": sql}


def and_(*clauses: dict[str, Any]) -> dict[str, Any]:
    return {"op": "and", "clauses": list(clauses)}


def or_(*clauses: dict[str, Any]) -> dict[str, Any]:
    return {"op": "or", "clauses": list(clauses)}


def not_(clause: dict[str, Any]) -> dict[str, Any]:
    return {"op": "not", "clause": clause}


class _LikeBuilder:
    def __init__(self, name: str):
        self._name = name

    def contains(self, value: str) -> dict[str, Any]:
        return {"op": "like", "column": self._name, "value": f"%{escape_like(value)}%"}

    def starts_with(self, value: str) -> dict[str, Any]:
        return {"op": "like", "column": self._name, "value": f"{escape_like(value)}%"}

    def ends_with(self, value: str) -> dict[str, Any]:
        return {"op": "like", "column": self._name, "value": f"%{escape_like(value)}"}

    def raw(self, value: str) -> dict[str, Any]:
        assert_safe_like_pattern(value)
        return {"op": "like", "column": self._name, "value": value}


class WhereBuilder:
    def __init__(self, name: str):
        self._name = name
        self.like = _LikeBuilder(name)

    def _binary(self, op: str, value: Any) -> dict[str, Any]:
        return {"op": op, "column": self._name, "value": value}

    def eq(self, value: Any) -> dict[str, Any]:
        return self._binary("eq", value)

    def ne(self, value: Any) -> dict[str, Any]:
        return self._binary("ne", value)

    def gt(self, value: Any) -> dict[str, Any]:
        return self._binary("gt", value)

    def gte(self, value: Any) -> dict[str, Any]:
        return self._binary("gte", value)

    def lt(self, value: Any) -> dict[str, Any]:
        return self._binary("lt", value)

    def lte(self, value: Any) -> dict[str, Any]:
        return self._binary("lte", value)

    def in_(self, values: list[Any]) -> dict[str, Any]:
        return {"op": "in", "column": self._name, "values": list(values)}


def where(column: DataColumn | str) -> WhereBuilder:
    name = column.name if isinstance(column, DataColumn) else column
    return WhereBuilder(name)


__all__ = [
    "MAX_LIKE_PATTERN_LENGTH",
    "MAX_CONSECUTIVE_WILDCARDS",
    "MAX_LIKE_ALTERNATION_SEGMENTS",
    "escape_like",
    "assert_safe_like_pattern",
    "raw",
    "and_",
    "or_",
    "not_",
    "where",
    "WhereBuilder",
]
