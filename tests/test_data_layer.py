"""Unit + wire tests for the ergonomic data layer.

These mirror the node data layer's behavior (the conformance runner only
exercises the operation-id route-table surface, not this fluent layer — see the
port report DoD #3). Covers: fluent surface, per_page clamp, offset pagination
envelope, legacy/v1/v2/invalid cursor rejection, where serialization incl. the
IN-comma guard and pushable-filter rejection, select validation + projection,
LIKE escaping + ReDoS guards, CRUD wire paths, list_all drift, discover (slug
inspect + appId fallback + TableNotFound), camelize-off row verbatimness, and
schema-cache LRU/TTL.
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from axhub_sdk import AxHubClient, TokenType
from axhub_sdk.data import (
    InvalidCursorError,
    LegacyCursorError,
    TableNotFoundError,
    ValidationError,
    and_,
    define_schema,
    not_,
    or_,
    where,
)
from axhub_sdk.data.pagination import (
    ListAllItem,
    PaginatedList,
    is_v2_cursor,
    list_all,
    serialize_order_by,
)
from axhub_sdk.data.projection import (
    project_row,
    serialize_select,
    validate_select_columns,
)
from axhub_sdk.data.schema_cache import SchemaCache
from axhub_sdk.data.where_serializer import serialize_where
from axhub_sdk.data.client import _clamp_per_page


# ----------------------------- mock data server ------------------------------

class _DataHandler(BaseHTTPRequestHandler):
    """Records the last request and replies from a per-test ``response`` dict."""

    last = {}
    response = {"status": 200, "body": {}}

    def log_message(self, *_a):
        return

    def _handle(self):
        length = int(self.headers.get("Content-Length") or "0")
        raw_body = self.rfile.read(length).decode() if length else ""
        parsed = urlparse(self.path)
        _DataHandler.last = {
            "method": self.command,
            "path": parsed.path,
            "query": parse_qs(parsed.query, keep_blank_values=True),
            "raw_query": parsed.query,
            "body": json.loads(raw_body) if raw_body else None,
            "headers": {k.lower(): v for k, v in self.headers.items()},
        }
        resp = _DataHandler.response
        body = json.dumps(resp.get("body") if resp.get("body") is not None else {}).encode()
        self.send_response(resp.get("status", 200))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PATCH = do_DELETE = _handle


class _ServerCase(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _DataHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._teardown)
        self.client = AxHubClient(
            base_url=f"http://127.0.0.1:{self.server.server_address[1]}",
            token="pat_x",
            token_type=TokenType.PAT,
        )

    def _teardown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def table(self, schema=None):
        t = schema if schema is not None else "orders"
        return self.client.tenant("acme").app("crm").data.table(t)

    def set_response(self, body, status=200):
        _DataHandler.response = {"status": status, "body": body}


# ------------------------------- pure units ----------------------------------

class WhereSerializerTest(unittest.TestCase):
    def test_atom_and_and_and_in(self):
        self.assertEqual(serialize_where(where("status").eq("paid")), {"status": "eq.paid"})
        self.assertEqual(
            serialize_where(and_(where("total").gte(10), where("status").ne("void"))),
            {"total": "gte.10", "status": "ne.void"},
        )
        self.assertEqual(serialize_where(where("id").in_(["a", "b"])), {"id": "in.a,b"})

    def test_bool_and_none_stringify_like_js(self):
        self.assertEqual(serialize_where(where("active").eq(True)), {"active": "eq.true"})
        self.assertEqual(serialize_where(where("deleted").eq(None)), {"deleted": "eq.null"})

    def test_repeated_column_collapses_to_list(self):
        out = serialize_where(and_(where("tag").eq("a"), where("tag").eq("b")))
        self.assertEqual(out, {"tag": ["eq.a", "eq.b"]})

    def test_in_comma_guard(self):
        with self.assertRaises(ValidationError) as cm:
            serialize_where(where("name").in_(["a,b"]))
        self.assertEqual(cm.exception.code, "filter_in_comma")

    def test_unsupported_filters_rejected(self):
        for expr in (or_(where("a").eq(1)), not_(where("a").eq(1)), {"op": "raw", "sql": "1=1"}):
            with self.assertRaises(ValidationError) as cm:
                serialize_where(expr)
            self.assertEqual(cm.exception.code, "unsupported_filter")

    def test_nested_and_is_not_pushable(self):
        with self.assertRaises(ValidationError) as cm:
            serialize_where(and_(and_(where("a").eq(1))))
        self.assertEqual(cm.exception.code, "unsupported_filter")


class OrderByTest(unittest.TestCase):
    def test_string_form_appends_id_tiebreaker(self):
        self.assertEqual(serialize_order_by("-total"), "-total,id")
        self.assertEqual(serialize_order_by("name"), "name,id")

    def test_field_list_form(self):
        self.assertEqual(serialize_order_by([{"field": "total", "dir": "desc"}]), "-total,id")

    def test_empty_is_none(self):
        self.assertIsNone(serialize_order_by(None))


class ClampPerPageTest(unittest.TestCase):
    def test_clamp_1_to_100(self):
        self.assertEqual(_clamp_per_page(0), 1)
        self.assertEqual(_clamp_per_page(50), 50)
        self.assertEqual(_clamp_per_page(1000), 100)
        self.assertEqual(_clamp_per_page(-5), 1)
        self.assertIsNone(_clamp_per_page(None))
        self.assertEqual(_clamp_per_page(float("inf")), 100)
        self.assertEqual(_clamp_per_page(12.9), 12)  # trunc


class SelectTest(unittest.TestCase):
    def test_serialize(self):
        self.assertEqual(serialize_select(["id", "total"]), "id,total")
        self.assertIsNone(serialize_select(None))

    def test_empty_select_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            validate_select_columns(None, [])
        self.assertEqual(cm.exception.code, "select_empty")

    def test_unknown_column_rejected_with_schema(self):
        schema = define_schema("orders", {"id": "uuid", "total": "number"})
        with self.assertRaises(ValidationError) as cm:
            validate_select_columns(schema, ["id", "nope"])
        self.assertEqual(cm.exception.code, "select_unknown_column")

    def test_project_row_narrows(self):
        self.assertEqual(project_row({"id": "x", "total": 5, "extra": 1}, ["id"]), {"id": "x"})


class CursorRejectionTest(_ServerCase):
    def test_after_before_direction_rejected(self):
        for kw in ({"after": "x"}, {"before": "x"}, {"direction": "forward"}):
            with self.assertRaises(LegacyCursorError):
                self.table().list(**kw)

    def test_v1_and_v2_cursor_rejected(self):
        with self.assertRaises(LegacyCursorError):
            self.table().list(cursor="v1:abc")
        with self.assertRaises(LegacyCursorError):
            self.table().list(cursor="v2:abc")

    def test_non_integer_cursor_rejected(self):
        with self.assertRaises(InvalidCursorError):
            self.table().list(cursor="abc")
        with self.assertRaises(InvalidCursorError):
            self.table().list(cursor="0")

    def test_oversized_cursor_rejected(self):
        with self.assertRaises(InvalidCursorError):
            self.table().list(cursor="1" * 5000)

    def test_bad_page_rejected(self):
        with self.assertRaises(InvalidCursorError):
            self.table().list(page=0)

    def test_is_v2_cursor_helper(self):
        self.assertTrue(is_v2_cursor("v2:x"))
        self.assertFalse(is_v2_cursor("3"))


class ListWireTest(_ServerCase):
    def test_list_query_and_envelope(self):
        self.set_response({"items": [{"id": "1", "created_at": "t"}], "page": 2, "per_page": 10, "has_more": True})
        result = self.table().list(
            where=where("status").eq("paid"),
            order_by="-total",
            select=["id", "created_at"],
            page=2,
            page_size=10,
        )
        last = _DataHandler.last
        self.assertEqual(last["method"], "GET")
        self.assertEqual(last["path"], "/data/acme/crm/orders")
        self.assertEqual(last["query"]["status"], ["eq.paid"])
        self.assertEqual(last["query"]["per_page"], ["10"])
        self.assertEqual(last["query"]["page"], ["2"])
        self.assertEqual(last["query"]["sort"], ["-total,id"])
        self.assertEqual(last["query"]["_select"], ["id,created_at"])
        self.assertEqual(last["headers"]["x-api-key"], "pat_x")
        # envelope mirrors node: next/first cursor are page numbers as strings
        self.assertEqual(result.next_cursor, "3")
        self.assertEqual(result.first_cursor, "1")
        self.assertTrue(result.has_next)
        self.assertTrue(result.has_prev)
        self.assertFalse(result.total_is_exact)

    def test_row_data_returned_verbatim_no_camelize(self):
        # snake_case keys in row data must NOT be rewritten (mirror node transport).
        self.set_response({"items": [{"id": "1", "created_at": "2020", "is_active": True}], "has_more": False})
        result = self.table().list(where=where("id").eq("1"))
        self.assertEqual(result.items[0], {"id": "1", "created_at": "2020", "is_active": True})
        self.assertIsNone(result.next_cursor)

    def test_page_1_omits_page_query(self):
        self.set_response({"items": [], "has_more": False})
        self.table().list(page=1, where=where("id").eq("1"))
        self.assertNotIn("page", _DataHandler.last["query"])

    def test_select_projects_client_side(self):
        self.set_response({"items": [{"id": "1", "total": 9, "secret": "x"}], "has_more": False})
        result = self.table().list(select=["id", "total"], where=where("id").eq("1"))
        self.assertEqual(result.items[0], {"id": "1", "total": 9})

    def test_filterless_list_passes_for_owner_scoped_tables(self):
        # Live contract 2026-06: the backend ACCEPTS unfiltered list/count on
        # owner-scoped tables (rows auto-scope to the caller). The 0.3.0
        # client-side pre-check wrongly blocked this — filterless calls must
        # reach the wire.
        self.set_response({"items": [{"id": "mine"}], "has_more": False})
        result = self.table().list()
        self.assertEqual(result.items[0]["id"], "mine")

    def test_backend_where_required_400_maps_to_validation_error(self):
        # Non-owner-scoped tables still get the mass-scan guard — server-side.
        # The SDK maps that 400 (code=required) onto the same actionable error.
        self.set_response(
            {"error": {"message": "최소 1개의 WHERE 필터가 필요해요", "code": "required",
                       "category": "validation", "retryable": False,
                       "fields": [{"name": "where", "code": "required"}]}},
            status=400,
        )
        tc = self.table()
        with self.assertRaises(ValidationError) as cm:
            tc.list()
        self.assertEqual(cm.exception.code, "where_required")
        with self.assertRaises(ValidationError) as cm2:
            tc.count()
        self.assertEqual(cm2.exception.code, "where_required")


class CrudWireTest(_ServerCase):
    def test_count(self):
        self.set_response({"count": 42})
        n = self.table().count(where=where("status").eq("paid"))
        self.assertEqual(n, 42)
        self.assertEqual(_DataHandler.last["path"], "/data/acme/crm/orders/_count")
        self.assertEqual(_DataHandler.last["query"]["status"], ["eq.paid"])

    def test_get(self):
        self.set_response({"id": "abc", "total": 5})
        row = self.table().get("abc", select=["id", "total"])
        self.assertEqual(row, {"id": "abc", "total": 5})
        self.assertEqual(_DataHandler.last["method"], "GET")
        self.assertEqual(_DataHandler.last["path"], "/data/acme/crm/orders/abc")
        self.assertEqual(_DataHandler.last["query"]["_select"], ["id,total"])

    def test_insert(self):
        self.set_response({"id": "new", "total": 7})
        out = self.table().insert({"total": 7})
        self.assertEqual(out, {"id": "new", "total": 7})
        self.assertEqual(_DataHandler.last["method"], "POST")
        self.assertEqual(_DataHandler.last["path"], "/data/acme/crm/orders")
        self.assertEqual(_DataHandler.last["body"], {"total": 7})

    def test_insert_many_loops(self):
        self.set_response({"id": "x"})
        out = self.table().insert_many([{"a": 1}, {"a": 2}])
        self.assertEqual(out["count"], 2)
        self.assertEqual(len(out["items"]), 2)

    def test_update(self):
        self.set_response({"id": "abc", "total": 9})
        out = self.table().update("abc", {"total": 9})
        self.assertEqual(_DataHandler.last["method"], "PATCH")
        self.assertEqual(_DataHandler.last["path"], "/data/acme/crm/orders/abc")
        self.assertEqual(out, {"id": "abc", "total": 9})

    def test_delete(self):
        self.set_response({}, status=204)
        self.assertIsNone(self.table().delete("abc"))
        self.assertEqual(_DataHandler.last["method"], "DELETE")
        self.assertEqual(_DataHandler.last["path"], "/data/acme/crm/orders/abc")


class ListAllTest(unittest.TestCase):
    def test_drives_pages_and_emits_drift(self):
        pages = [
            PaginatedList(items=[{"id": 1}], next_cursor="2", total=2),
            PaginatedList(items=[{"id": 2}], next_cursor=None, total=3),  # total grew -> drift
        ]
        calls = {"i": 0}

        def fetcher(_opts):
            page = pages[calls["i"]]
            calls["i"] += 1
            return page

        out = list(list_all(fetcher))
        kinds = [(x.type, x.value if x.type == "item" else x.added_since) for x in out]
        self.assertEqual(kinds, [("item", {"id": 1}), ("drift", 1), ("item", {"id": 2})])


class DiscoverTest(_ServerCase):
    def test_discover_slug_inspect(self):
        self.set_response({
            "tableName": "orders",
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "total", "type": "numeric"},
                {"name": "__proto__", "type": "text"},  # must be skipped
                {"name": "ok name", "type": "text"},  # invalid identifier -> skipped
            ],
        })
        tc = self.client.tenant("acme").app("crm").data.discover("orders")
        self.assertEqual(_DataHandler.last["path"], "/api/v1/tenants/acme/apps/crm/tables/orders/inspect")
        self.assertEqual(tc.schema.columns, {"id": "uuid", "total": "number"})

    def test_discover_caches_across_chains(self):
        # The schema cache is memoized on the client, so two discover() calls from
        # separate tenant().app() chains hit the inspect endpoint ONCE (node parity:
        # `data` is one per-SDK DataClient whose cache persists).
        self.set_response({"tableName": "orders", "columns": [{"name": "id", "type": "uuid"}]})
        _DataHandler.last = {}
        self.client.tenant("acme").app("crm").data.discover("orders")
        first = _DataHandler.last.get("path")
        _DataHandler.last = {}
        self.client.tenant("acme").app("crm").data.discover("orders")
        # Second discover served from cache: server saw no new request.
        self.assertEqual(first, "/api/v1/tenants/acme/apps/crm/tables/orders/inspect")
        self.assertEqual(_DataHandler.last, {})

    def test_discover_404_becomes_table_not_found(self):
        # slug inspect 404 -> appId fallback hits bare /api/v1/apps which also
        # returns 404 -> normalized to TableNotFoundError.
        self.set_response({"error": {"code": "not_found", "category": "not_found"}}, status=404)
        with self.assertRaises(TableNotFoundError):
            self.client.tenant("acme").app("crm").data.discover("ghosts")


class SchemaCacheTest(unittest.TestCase):
    def test_get_or_set_caches(self):
        cache = SchemaCache()
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return define_schema("orders", {"id": "uuid"})

        cache.get_or_set("k", loader)
        cache.get_or_set("k", loader)
        self.assertEqual(calls["n"], 1)
        cache.invalidate("k")
        cache.get_or_set("k", loader)
        self.assertEqual(calls["n"], 2)

    def test_lru_eviction(self):
        cache = SchemaCache(max_entries=2)
        for k in ("a", "b", "c"):
            cache.set(k, define_schema(k, {"id": "uuid"}))
        self.assertIsNone(cache.get("a"))  # evicted
        self.assertIsNotNone(cache.get("c"))


class LikeGuardTest(unittest.TestCase):
    def test_contains_escapes_wildcards(self):
        expr = where("name").like.contains("50%_off")
        self.assertEqual(expr["value"], "%50\\%\\_off%")

    def test_like_raw_redos_guard(self):
        with self.assertRaises(ValidationError):
            where("name").like.raw("%%%%x")


if __name__ == "__main__":
    unittest.main()
