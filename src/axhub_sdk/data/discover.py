"""Runtime schema introspection via the table ``/inspect`` endpoint, with an
appId-resolution fallback and error normalization (mirrors node discover.ts).

Primary:  GET /api/v1/tenants/{t}/apps/{a}/tables/{table}/inspect
Fallback: on 404, resolve appId by scanning GET /api/v1/apps?tenant_slug=...,
          then GET /api/v1/apps/{appId}/tables/{table}.
Neither endpoint has a generated operation-id, so discover goes through the
raw-path transport. ``camelize=True`` here so ``table_name``/``tableName`` both
resolve (inspect payload is metadata, not user row data).
"""
from __future__ import annotations

import time
from typing import Any
from urllib import parse

from .. import AxHubError
from .dsl.schema import DataTableSchema, define_schema
from .errors import IntrospectFailedError, ScanLimitExceededError, TableNotFoundError

APP_LOOKUP_PAGE_SIZE = 100
APP_LOOKUP_MAX_PAGES = 10
APP_LOOKUP_BUDGET_MS = 5_000

_FORBIDDEN_COLUMN_NAMES = {"__proto__", "constructor", "prototype"}
import re as _re

_COLUMN_NAME_RE = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _encode(value: str) -> str:
    return parse.quote(str(value), safe="")


def fetch_discovered_schema(client, tenant_slug: str, app_slug: str, table: str, *, fresh: bool | None = None, ttl_ms: int | None = None) -> DataTableSchema:
    # The appId path is the route the `axhub` CLI uses and is verified to work with
    # a data-ring PAT (2026-06). The slug `/inspect` route rejects a slug in the
    # {tenant} path segment on the live backend ("tenant_id 형식이 잘못됐어요", HTTP
    # 400) — a 400 not a 404, so the old slug-first order never reached this working
    # path. appId is primary; slug inspect is a best-effort fallback. The appId error
    # is the meaningful one, so it is what surfaces.
    try:
        return _fetch_app_id_inspect(client, tenant_slug, app_slug, table)
    except Exception as err:
        try:
            return _fetch_slug_inspect(client, tenant_slug, app_slug, table)
        except Exception:
            raise _normalize_discover_error(err, tenant_slug, app_slug, table)


def _fetch_slug_inspect(client, tenant_slug: str, app_slug: str, table: str) -> DataTableSchema:
    path = f"/api/v1/tenants/{_encode(tenant_slug)}/apps/{_encode(app_slug)}/tables/{_encode(table)}/inspect"
    raw = client.request_raw("GET", path, camelize=True)
    return schema_from_inspect_result(table, raw)


def _fetch_app_id_inspect(client, tenant_slug: str, app_slug: str, table: str) -> DataTableSchema:
    app_id = _resolve_app_id(client, tenant_slug, app_slug)
    if not app_id:
        raise TableNotFoundError(f"Dynamic data table '{table}' was not found")
    path = f"/api/v1/apps/{_encode(app_id)}/tables/{_encode(table)}"
    raw = client.request_raw("GET", path, camelize=True)
    return schema_from_inspect_result(table, raw)


def _resolve_app_id(client, tenant_slug: str, app_slug: str) -> str | None:
    started_at = time.monotonic() * 1000.0
    cursor: str | None = None
    for page in range(APP_LOOKUP_MAX_PAGES):
        if time.monotonic() * 1000.0 - started_at > APP_LOOKUP_BUDGET_MS:
            raise IntrospectFailedError(
                f"app lookup budget exceeded ({APP_LOOKUP_BUDGET_MS}ms) while searching for slug '{app_slug}' in tenant '{tenant_slug}'"
            )
        query: dict[str, Any] = {"tenant_slug": tenant_slug, "limit": APP_LOOKUP_PAGE_SIZE}
        if cursor:
            query["cursor"] = cursor
        raw = client.request_raw("GET", "/api/v1/apps", query=query, camelize=True)
        items = (raw or {}).get("items") or []
        match = next((app for app in items if app.get("slug") == app_slug and isinstance(app.get("id"), str)), None)
        if match and match.get("id"):
            return match["id"]
        # Empty page on the first request means the tenant truly has no apps.
        if page == 0 and len(items) == 0:
            return None
        next_cursor = (raw or {}).get("next_cursor") or (raw or {}).get("nextCursor")
        if not next_cursor:
            return None
        cursor = next_cursor
    raise ScanLimitExceededError(
        f"App lookup exceeded {APP_LOOKUP_MAX_PAGES} pages x {APP_LOOKUP_PAGE_SIZE} apps without finding slug '{app_slug}'"
    )


def _normalize_discover_error(err: Exception, tenant_slug: str, app_slug: str, table: str) -> Exception:
    if isinstance(err, (TableNotFoundError, IntrospectFailedError, ScanLimitExceededError)):
        return err
    if _is_not_found(err):
        return TableNotFoundError(
            f"Dynamic data table '{table}' was not found",
            request_id=getattr(err, "request_id", None),
        )
    status = getattr(err, "status", None)
    if isinstance(status, int) and status >= 500:
        return IntrospectFailedError(
            f"Failed to introspect dynamic data table '{table}'",
            status=status,
            retryable=bool(getattr(err, "retryable", False)),
            request_id=getattr(err, "request_id", None),
        )
    return err if isinstance(err, Exception) else Exception(str(err))


def schema_from_inspect_result(table: str, raw: Any) -> DataTableSchema:
    raw = raw or {}
    columns = raw.get("columns") or []
    shape: dict[str, Any] = {}
    for column in columns:
        name = column.get("name")
        if name in _FORBIDDEN_COLUMN_NAMES:
            continue
        if not isinstance(name, str) or not _COLUMN_NAME_RE.match(name):
            continue
        shape[name] = _column_type_to_def(column.get("type"))
    table_name = raw.get("tableName") or raw.get("table_name") or raw.get("name") or table
    return define_schema({"table": table_name, "columns": shape})


def _column_type_to_def(col_type: Any) -> str:
    if col_type == "uuid":
        return "uuid"
    if col_type in {"int", "integer", "bigint"}:
        return "integer"
    if col_type in {"float", "numeric", "double precision", "real"}:
        return "number"
    if col_type in {"bool", "boolean"}:
        return "boolean"
    if col_type in {"timestamp", "timestamptz", "timestamp with time zone"}:
        return "timestamp"
    if col_type in {"json", "jsonb"}:
        return "json"
    # text / varchar / character varying / unknown -> string
    return "string"


def _is_not_found(err: Exception) -> bool:
    if isinstance(err, TableNotFoundError):
        return True
    return isinstance(err, AxHubError) and getattr(err, "status", None) == 404


__all__ = ["fetch_discovered_schema", "schema_from_inspect_result"]
