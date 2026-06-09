"""Optional schema validation hook (mirrors node dsl/zod.ts).

The SDK duck-types a Pydantic/attrs/zod-style validator so the validation
library stays an optional dependency and is never imported. A validator is
"schema-like" if it exposes a callable ``safe_parse`` (or ``safeParse``).
On ``update`` a ``partial()`` variant is used when available.
"""
from __future__ import annotations

from typing import Any

from .schema import DataTableSchema
from ..errors import ValidationError
from ... import AxHubError


def is_validator_like(value: Any) -> bool:
    return value is not None and (callable(getattr(value, "safe_parse", None)) or callable(getattr(value, "safeParse", None)))


def _safe_parse(validator: Any, data: Any) -> Any:
    fn = getattr(validator, "safe_parse", None) or getattr(validator, "safeParse", None)
    return fn(data)


def run_schema_validation(schema: DataTableSchema | None, data: Any, mode: str) -> None:
    """Validate ``data`` against ``schema.validate`` before any network request.
    ``mode`` is "insert" or "update" (update uses ``partial()`` when available)."""
    validator = schema.validate if schema is not None else None
    if validator is None:
        return
    if not is_validator_like(validator):
        raise AxHubError(
            "configuration",
            "validator_missing",
            "define_schema validate option requires a schema-like object with safe_parse()",
            0,
            False,
        )
    effective = validator
    if mode == "update" and callable(getattr(validator, "partial", None)):
        effective = validator.partial()
    result = _safe_parse(effective, data)
    success = getattr(result, "success", None)
    if success is None and isinstance(result, dict):
        success = result.get("success")
    if success:
        return
    error = getattr(result, "error", None)
    if error is None and isinstance(result, dict):
        error = result.get("error")
    issues = getattr(error, "issues", None)
    if issues is None and isinstance(error, dict):
        issues = error.get("issues")
    issues = issues or []
    count = len(issues) or 1
    raise ValidationError(
        f"{count} validation failure{'' if count == 1 else 's'} before network request",
        "validation_failed",
    )


__all__ = ["is_validator_like", "run_schema_validation"]
