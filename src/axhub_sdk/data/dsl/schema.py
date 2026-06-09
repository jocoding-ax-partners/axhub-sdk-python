"""Schema definitions and ``define_schema`` (mirrors node dsl/schema.ts).

Column defs are either a primitive type string or an enum descriptor
``{"type": "enum", "values": [...]}``. ``define_schema`` builds the ``cols``
accessor map used by the ``where(schema.cols.x)`` typed DSL path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# uuid | string | number | integer | boolean | timestamp | json, or an enum descriptor.
ColumnPrimitive = str
ColumnDef = Any  # str | {"type": "enum", "values": [...]}
SchemaShape = dict[str, ColumnDef]


@dataclass(frozen=True)
class DataColumn:
    table: str
    name: str
    definition: ColumnDef


@dataclass(frozen=True)
class DataTableSchema:
    table: str
    columns: SchemaShape
    cols: dict[str, DataColumn]
    validate: Any = None  # zod-compatible validator (duck-typed safe_parse / safeParse)


def _is_schema(value: Any) -> bool:
    return isinstance(value, DataTableSchema) or (
        isinstance(value, Mapping) and "table" in value and "columns" in value and "cols" in value
    )


def define_schema(table_or_input, columns: Mapping[str, ColumnDef] | None = None, *, validate: Any = None) -> DataTableSchema:
    """Define a data table schema.

    Two call shapes mirror node's two overloads:
      define_schema("orders", {"id": "uuid", "total": "number"})
      define_schema({"table": "orders", "columns": {...}}, validate=...)
    An existing DataTableSchema is re-wrapped, optionally attaching ``validate``.
    """
    if isinstance(table_or_input, DataTableSchema):
        return DataTableSchema(
            table=table_or_input.table,
            columns=table_or_input.columns,
            cols=table_or_input.cols,
            validate=validate if validate is not None else table_or_input.validate,
        )
    if isinstance(table_or_input, Mapping):
        table = table_or_input["table"]
        shape: SchemaShape = dict(table_or_input["columns"])
    else:
        table = table_or_input
        if columns is None:
            raise ValueError("define_schema requires columns when called with a table name")
        shape = dict(columns)
    cols = {name: DataColumn(table=table, name=name, definition=definition) for name, definition in shape.items()}
    return DataTableSchema(table=table, columns=shape, cols=cols, validate=validate)


__all__ = ["ColumnDef", "SchemaShape", "DataColumn", "DataTableSchema", "define_schema"]
