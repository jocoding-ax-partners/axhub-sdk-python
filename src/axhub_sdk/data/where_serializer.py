"""Serialize the predicate DSL into backend filter query params
(mirrors node where-serializer.ts).

Each pushable atom becomes ``column=<op>.<value>`` (PostgREST-style). Repeated
columns collapse into a list so the transport emits repeated query params
(``urlencode(..., doseq=True)``). Only top-level ``and(...)`` of pushable atoms
and bare atoms are accepted; or/not/raw and nested and raise ValidationError —
this matches the live backend's filter grammar (see node, gap-matrix S7-S9).
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from .errors import ValidationError

_PUSHABLE_BINARY = {"eq", "ne", "gt", "gte", "lt", "lte", "like"}


def serialize_where(expr: dict[str, Any] | None) -> dict[str, Any]:
    if expr is None:
        return {}
    out: dict[str, Any] = {}
    for f in _collect_pushable_filters(expr, allow_and=True):
        _append_query(out, f["column"], f["value"])
    return out


def _append_query(out: dict[str, Any], key: str, value: str) -> None:
    existing = out.get(key)
    if key not in out:
        out[key] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        out[key] = [existing, value]


def _collect_pushable_filters(expr: dict[str, Any], *, allow_and: bool) -> list[dict[str, str]]:
    op = expr.get("op")
    if op in _PUSHABLE_BINARY:
        return [{"column": expr["column"], "value": f"{op}.{_stringify(expr['value'])}"}]
    if op == "in":
        values = [_stringify(v) for v in expr["values"]]
        bad = next((v for v in values if "," in v), None)
        if bad is not None:
            raise ValidationError(
                f"IN filter values cannot contain commas because the live backend uses comma-separated IN lists (bad value: {bad})",
                "filter_in_comma",
            )
        return [{"column": expr["column"], "value": "in." + ",".join(values)}]
    if op == "and" and allow_and:
        out: list[dict[str, str]] = []
        for clause in expr["clauses"]:
            out.extend(_collect_pushable_filters(clause, allow_and=False))
        return out
    # or / not / raw / nested-and all fall through to the rejection below.
    raise ValidationError(
        f"Data where clause '{op}' cannot be pushed to the live backend; use top-level and(eq/ne/gt/gte/lt/lte/in/like) only",
        "unsupported_filter",
    )


def _stringify(value: Any) -> str:
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if value is None:
        return "null"
    if isinstance(value, bool):
        # bool before int/str: mirror JS String(true) -> "true"
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value)


__all__ = ["serialize_where"]
