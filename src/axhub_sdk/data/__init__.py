"""Ergonomic data layer for the AX Hub Python SDK.

Public surface (mirrors the node ``resources/data`` layer):

    sdk.tenant(tenant_slug).app(app_slug).data.table(name_or_schema)
    sdk.tenant(tenant_slug).app(app_slug).data.discover(table)

returns a ``DataTableClient`` with ``list`` / ``list_all`` / ``count`` / ``get``
/ ``insert`` / ``insert_many`` / ``update`` / ``delete``, plus the predicate DSL
(``where(col).eq(v)`` / ``and_(...)``), ``define_schema(...)``, and offset-only
pagination.
"""
from __future__ import annotations

from .client import AppDataFactory, DataClient, DataTableClient, TenantDataFactory
from .discover import fetch_discovered_schema, schema_from_inspect_result
from .dsl import (
    DataColumn,
    DataTableSchema,
    WhereBuilder,
    and_,
    assert_safe_like_pattern,
    define_schema,
    escape_like,
    not_,
    or_,
    raw,
    run_schema_validation,
    where,
)
from .errors import (
    IntrospectFailedError,
    InvalidCursorError,
    LegacyCursorError,
    ScanLimitExceededError,
    TableNotFoundError,
    ValidationError,
)
from .pagination import ListAllItem, PaginatedList, is_v2_cursor, serialize_order_by
from .projection import project_row, project_rows, serialize_select, validate_select_columns
from .schema_cache import SchemaCache, schema_cache_key
from .where_serializer import serialize_where

__all__ = [
    # fluent + table client
    "DataClient",
    "TenantDataFactory",
    "AppDataFactory",
    "DataTableClient",
    # dsl
    "define_schema",
    "DataTableSchema",
    "DataColumn",
    "where",
    "WhereBuilder",
    "and_",
    "or_",
    "not_",
    "raw",
    "escape_like",
    "assert_safe_like_pattern",
    "run_schema_validation",
    # pagination / projection
    "PaginatedList",
    "ListAllItem",
    "serialize_order_by",
    "is_v2_cursor",
    "serialize_select",
    "serialize_where",
    "validate_select_columns",
    "project_row",
    "project_rows",
    # discover + cache
    "fetch_discovered_schema",
    "schema_from_inspect_result",
    "SchemaCache",
    "schema_cache_key",
    # errors
    "ValidationError",
    "LegacyCursorError",
    "InvalidCursorError",
    "TableNotFoundError",
    "IntrospectFailedError",
    "ScanLimitExceededError",
]
