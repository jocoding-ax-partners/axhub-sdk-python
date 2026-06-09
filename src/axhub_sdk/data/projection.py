"""Column projection: ``select`` serialization, validation, and client-side
row narrowing (mirrors node projection.ts).

``serialize_select`` joins columns with commas into the ``_select`` query param.
``validate_select_columns`` rejects an empty select and, when a schema is known,
unknown columns. ``project_row``/``project_rows`` narrow returned rows to the
selected keys client-side.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .dsl.schema import DataTableSchema
from .errors import ValidationError


def serialize_select(select: Sequence[str] | None) -> str | None:
    if select is None:
        return None
    return ",".join(select)


def validate_select_columns(schema: DataTableSchema | None, select: Sequence[str] | None) -> None:
    if select is None:
        return
    if len(select) == 0:
        raise ValidationError(
            "select must include at least one column; omit select to fetch full rows",
            "select_empty",
        )
    if schema is None:
        return
    allowed = set(schema.columns.keys())
    invalid = [c for c in select if c not in allowed]
    if not invalid:
        return
    plural = "" if len(invalid) == 1 else "s"
    raise ValidationError(
        f"select contains unknown column{plural}: {', '.join(invalid)}",
        "select_unknown_column",
    )


def project_row(row: Mapping[str, Any], select: Sequence[str] | None) -> dict[str, Any]:
    if select is None:
        return dict(row)
    return {k: row[k] for k in select if k in row}


def project_rows(rows: Sequence[Mapping[str, Any]], select: Sequence[str] | None) -> list[dict[str, Any]]:
    if select is None:
        return [dict(r) for r in rows]
    return [project_row(r, select) for r in rows]


__all__ = ["serialize_select", "validate_select_columns", "project_row", "project_rows"]
