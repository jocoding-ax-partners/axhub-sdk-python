"""Per-client schema cache for runtime ``data.discover()`` (mirrors node
schema-cache.ts).

Uses ``OrderedDict`` for deterministic LRU eviction (move-to-end on read/write)
and a negative-TTL stale-while-error window: a transient 5xx during refresh
keeps the previous entry alive briefly instead of evicting it. The node version
de-dupes concurrent in-flight loads; the sync Python port omits the in-flight
map (no concurrency within a single synchronous call) — see gap-matrix.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from .dsl.schema import DataTableSchema

DEFAULT_SCHEMA_CACHE_TTL_MS = 5 * 60_000
DEFAULT_SCHEMA_CACHE_MAX_ENTRIES = 1000
DEFAULT_SCHEMA_CACHE_NEGATIVE_TTL_MS = 30_000


def _now_ms() -> float:
    return time.monotonic() * 1000.0


def _is_transient_server_error(err: Exception) -> bool:
    status = getattr(err, "status", None)
    return isinstance(status, int) and status >= 500


@dataclass
class _Entry:
    schema: DataTableSchema
    expires_at: float


def schema_cache_key(tenant_slug: str, app_slug: str, table: str) -> str:
    return f"{tenant_slug}/{app_slug}/{table}"


class SchemaCache:
    def __init__(self, max_entries: int | None = None, ttl_ms: int | None = None, negative_ttl_ms: int | None = None):
        self._store: "OrderedDict[str, _Entry]" = OrderedDict()
        self._max_entries = max(1, max_entries if max_entries is not None else DEFAULT_SCHEMA_CACHE_MAX_ENTRIES)
        self._ttl_ms = max(1, ttl_ms if ttl_ms is not None else DEFAULT_SCHEMA_CACHE_TTL_MS)
        self._negative_ttl_ms = max(0, negative_ttl_ms if negative_ttl_ms is not None else DEFAULT_SCHEMA_CACHE_NEGATIVE_TTL_MS)

    @property
    def size(self) -> int:
        return len(self._store)

    def get(self, key: str) -> DataTableSchema | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= _now_ms():
            del self._store[key]
            return None
        self._store.move_to_end(key)  # refresh recency
        return entry.schema

    def set(self, key: str, schema: DataTableSchema, ttl_ms: int | None = None) -> None:
        self._store.pop(key, None)
        self._store[key] = _Entry(schema=schema, expires_at=_now_ms() + max(1, ttl_ms if ttl_ms is not None else self._ttl_ms))
        self._evict_overflow()

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._store.clear()
            return
        self._store.pop(key, None)

    def get_or_set(self, key: str, loader: Callable[[], DataTableSchema], *, fresh: bool | None = None, ttl_ms: int | None = None) -> DataTableSchema:
        if not fresh:
            cached = self.get(key)
            if cached is not None:
                return cached
        previous = self._store.get(key)
        try:
            schema = loader()
        except Exception as err:
            if previous is not None and self._negative_ttl_ms > 0 and _is_transient_server_error(err):
                self._store.pop(key, None)
                self._store[key] = _Entry(schema=previous.schema, expires_at=_now_ms() + self._negative_ttl_ms)
            raise
        self.set(key, schema, ttl_ms)
        return schema

    def _evict_overflow(self) -> None:
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)  # oldest


__all__ = [
    "DEFAULT_SCHEMA_CACHE_TTL_MS",
    "DEFAULT_SCHEMA_CACHE_MAX_ENTRIES",
    "DEFAULT_SCHEMA_CACHE_NEGATIVE_TTL_MS",
    "SchemaCache",
    "schema_cache_key",
]
