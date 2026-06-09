"""Ergonomic data layer: fluent builder + dynamic-table CRUD + offset
pagination (mirrors node index.ts DataClient / TenantDataFactory /
AppDataFactory / DataTableClient).

Wire paths (EXACTLY as node, via the raw-path transport so row bodies and the
list envelope are returned verbatim, no snake->camel rewriting):
  list / insert        GET|POST   /data/{tenant}/{app}/{table}
  get / update / delete GET|PATCH|DELETE /data/{tenant}/{app}/{table}/{id}
  count                GET        /data/{tenant}/{app}/{table}/_count
"""
from __future__ import annotations

import math
from typing import Any, Iterator, Sequence
from urllib import parse

from .discover import fetch_discovered_schema
from .dsl.schema import DataTableSchema
from .dsl.validation import run_schema_validation
from .errors import InvalidCursorError, LegacyCursorError, ValidationError
from .pagination import (
    MAX_CURSOR_TOKEN_LENGTH,
    ListAllItem,
    PaginatedList,
    is_v2_cursor,
    list_all,
    serialize_order_by,
)
from .projection import project_row, project_rows, serialize_select, validate_select_columns
from .schema_cache import SchemaCache, schema_cache_key
from .where_serializer import serialize_where


def _encode(value: str) -> str:
    return parse.quote(str(value), safe="")


def _clamp_per_page(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return 100
    return min(100, max(1, int(value)))


def _reject_legacy_page_options(after: Any, before: Any, direction: Any, table_name: str) -> None:
    if after is not None or before is not None or direction is not None:
        raise LegacyCursorError(
            "after/before keyset cursors are not supported by the live AX Hub data API; use cursor/page numeric offset pagination",
        )


def _validate_plain_cursor(cursor: str, table_name: str) -> None:
    if len(cursor) > MAX_CURSOR_TOKEN_LENGTH:
        raise InvalidCursorError(f"Cursor token exceeds maximum size ({MAX_CURSOR_TOKEN_LENGTH} chars)")
    if cursor.startswith("v1:"):
        raise LegacyCursorError(
            "Legacy v1: cursor token is not compatible with AX Hub offset-only pagination; restart pagination without cursor",
        )
    if is_v2_cursor(cursor):
        raise LegacyCursorError(
            "v2 keyset cursors are not supported by the live AX Hub data API; restart pagination and use the numeric cursor returned by list()",
        )
    try:
        parsed = int(cursor)
    except (TypeError, ValueError):
        raise InvalidCursorError("Plain cursor must be a positive integer page or a v2: keyset token")
    if parsed < 1:
        raise InvalidCursorError("Plain cursor must be a positive integer page or a v2: keyset token")


def _resolve_offset_page(cursor: Any, page: Any, table_name: str) -> int:
    if cursor is not None:
        _validate_plain_cursor(cursor, table_name)
        return int(cursor)
    if page is None:
        return 1
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise InvalidCursorError("page must be a positive integer")
    return page


class DataTableClient:
    """Client bound to one ``{tenant}/{app}/{table}`` with CRUD + pagination."""

    def __init__(self, client, tenant_slug: str, app_slug: str, table_name: str, schema: DataTableSchema | None = None):
        self._client = client
        self._tenant_slug = tenant_slug
        self._app_slug = app_slug
        self._table_name = table_name
        self.schema = schema

    def _path(self, row_id: str | None = None) -> str:
        base = f"/data/{_encode(self._tenant_slug)}/{_encode(self._app_slug)}/{_encode(self._table_name)}"
        return base if row_id is None else f"{base}/{_encode(row_id)}"

    def list(
        self,
        *,
        where: dict | None = None,
        order_by: Any = None,
        select: Sequence[str] | None = None,
        page: int | None = None,
        page_size: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        after: Any = None,
        before: Any = None,
        direction: Any = None,
    ) -> PaginatedList:
        validate_select_columns(self.schema, select)
        _reject_legacy_page_options(after, before, direction, self._table_name)
        resolved_page = _resolve_offset_page(cursor, page, self._table_name)
        per_page = _clamp_per_page(page_size if page_size is not None else limit)
        # The AxHub data ring rejects an unfiltered list with HTTP 400
        # ("최소 1개의 WHERE 필터가 필요해요") as a deliberate mass-scan guard —
        # confirmed live 2026-06, mirrored by the `axhub data` CLI. Checked after
        # cursor/page validation so a malformed cursor still surfaces first.
        if where is None:
            raise ValidationError(
                "AxHub data list requires at least one WHERE filter "
                "(the backend rejects unfiltered scans). Pass `where=...`.",
                "where_required",
            )
        query: dict[str, Any] = dict(serialize_where(where))
        if per_page is not None:
            query["per_page"] = per_page
        if resolved_page != 1:
            query["page"] = resolved_page
        sort = serialize_order_by(order_by)
        if sort:
            query["sort"] = sort
        serialized_select = serialize_select(select)
        if serialized_select is not None:
            query["_select"] = serialized_select
        raw = self._client.request_raw("GET", self._path(), query=query) or {}
        items = project_rows(raw.get("items") or [], select)
        # NOTE: mirrors node behavior — current_page falls back to the requested
        # page, has_next reads the backend `has_more` flag verbatim, has_prev is
        # derived client-side from the page number (see gap-matrix S7-S9).
        current_page = raw.get("page") if raw.get("page") is not None else resolved_page
        has_next = bool(raw.get("has_more") or False)
        has_prev = current_page > 1
        return PaginatedList(
            items=items,
            next_cursor=str(current_page + 1) if has_next else None,
            first_cursor=str(current_page - 1) if has_prev else None,
            has_next=has_next,
            has_prev=has_prev,
            total_is_exact=False,
        )

    def list_all(
        self,
        *,
        where: dict | None = None,
        order_by: Any = None,
        select: Sequence[str] | None = None,
        page_size: int | None = None,
        limit: int | None = None,
    ) -> Iterator[ListAllItem]:
        base = {"where": where, "order_by": order_by, "select": select, "limit": limit}

        def fetcher(p: dict[str, Any]) -> PaginatedList:
            kwargs = {k: v for k, v in base.items() if v is not None}
            if p.get("cursor") is not None:
                kwargs["cursor"] = p["cursor"]
            ps = p.get("page_size") if p.get("page_size") is not None else page_size
            if ps is not None:
                kwargs["page_size"] = ps
            return self.list(**kwargs)

        return list_all(fetcher, {"page_size": page_size})

    def count(self, *, where: dict | None = None) -> int:
        # Same mass-scan guard as list() — the backend 400s an unfiltered count.
        if where is None:
            raise ValidationError(
                "AxHub data count requires at least one WHERE filter "
                "(the backend rejects unfiltered scans). Pass `where=...`.",
                "where_required",
            )
        raw = self._client.request_raw("GET", f"{self._path()}/_count", query=serialize_where(where)) or {}
        return raw.get("count")

    def get(self, row_id: str, *, select: Sequence[str] | None = None) -> dict[str, Any]:
        validate_select_columns(self.schema, select)
        serialized_select = serialize_select(select)
        query = None if serialized_select is None else {"_select": serialized_select}
        row = self._client.request_raw("GET", self._path(row_id), query=query) or {}
        return project_row(row, select)

    def insert(self, row: dict[str, Any]) -> dict[str, Any]:
        run_schema_validation(self.schema, row, "insert")
        return self._client.request_raw("POST", self._path(), body=row)

    def insert_many(self, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        for row in rows:
            run_schema_validation(self.schema, row, "insert")
        # NOTE: mirrors node behavior — no bulk endpoint exists, so insertMany
        # loops single inserts and returns {items, count} (see gap-matrix).
        items = [self.insert(row) for row in rows]
        return {"items": items, "count": len(items)}

    def update(self, row_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        run_schema_validation(self.schema, patch, "update")
        return self._client.request_raw("PATCH", self._path(row_id), body=patch)

    def delete(self, row_id: str) -> None:
        self._client.request_raw("DELETE", self._path(row_id))
        return None


class AppDataFactory:
    def __init__(self, data: "DataClient", tenant_slug: str, app_slug: str):
        self._data = data
        self._tenant_slug = tenant_slug
        self._app_slug = app_slug

    def table(self, table: str | DataTableSchema) -> DataTableClient:
        return self._data.table(self._tenant_slug, self._app_slug, table)

    def discover(self, table: str, *, fresh: bool | None = None, ttl_ms: int | None = None) -> DataTableClient:
        return self._data.discover(self._tenant_slug, self._app_slug, table, fresh=fresh, ttl_ms=ttl_ms)

    def invalidate_schema(self, table: str | None = None) -> None:
        if table is None:
            self._data.invalidate_schema()
        else:
            self._data.invalidate_schema(self._tenant_slug, self._app_slug, table)


class TenantDataFactory:
    def __init__(self, data: "DataClient", tenant_slug: str):
        self._data = data
        self._tenant_slug = tenant_slug

    def app(self, app_slug: str) -> AppDataFactory:
        return AppDataFactory(self._data, self._tenant_slug, app_slug)


class DataClient:
    """Entry point for the ergonomic data layer; holds the per-client schema
    cache used by ``discover()`` (mirrors node DataClient)."""

    def __init__(self, client, schema_cache: "SchemaCache | dict | None" = None):
        self._client = client
        if isinstance(schema_cache, SchemaCache):
            self._schema_cache = schema_cache
        elif isinstance(schema_cache, dict):
            # node accepts SchemaCacheOptions; mirror with a dict of {max_entries, ttl_ms, negative_ttl_ms}.
            self._schema_cache = SchemaCache(**schema_cache)
        else:
            self._schema_cache = SchemaCache()

    def table(self, tenant_slug: str, app_slug: str, table: str | DataTableSchema) -> DataTableClient:
        schema = table if isinstance(table, DataTableSchema) else None
        table_name = table.table if isinstance(table, DataTableSchema) else table
        return DataTableClient(self._client, tenant_slug, app_slug, table_name, schema)

    def scoped(self, tenant_slug: str) -> TenantDataFactory:
        return TenantDataFactory(self, tenant_slug)

    def discover(self, tenant_slug: str, app_slug: str, table: str, *, fresh: bool | None = None, ttl_ms: int | None = None) -> DataTableClient:
        key = schema_cache_key(tenant_slug, app_slug, table)
        schema = self._schema_cache.get_or_set(
            key,
            lambda: fetch_discovered_schema(self._client, tenant_slug, app_slug, table, fresh=fresh, ttl_ms=ttl_ms),
            fresh=fresh,
            ttl_ms=ttl_ms,
        )
        return DataTableClient(self._client, tenant_slug, app_slug, schema.table, schema)

    def invalidate_schema(self, tenant_slug: str | None = None, app_slug: str | None = None, table: str | None = None) -> None:
        if tenant_slug is not None and app_slug is not None and table is not None:
            self._schema_cache.invalidate(schema_cache_key(tenant_slug, app_slug, table))
            return
        self._schema_cache.invalidate()


__all__ = [
    "DataTableClient",
    "AppDataFactory",
    "TenantDataFactory",
    "DataClient",
]
