import asyncio
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from axhub_sdk import AsyncAxHubClient, AxHubClient, AxHubError, TokenType


class _RawDbHandler(BaseHTTPRequestHandler):
    body = {}
    seen = {}

    def do_GET(self):
        parsed = urlparse(self.path)
        _RawDbHandler.seen = {"path": parsed.path, "query": parse_qs(parsed.query)}
        raw = json.dumps(_RawDbHandler.body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        return


class RawDbTest(unittest.TestCase):
    def _client(self, body):
        _RawDbHandler.body = body
        _RawDbHandler.seen = {}
        server = HTTPServer(("127.0.0.1", 0), _RawDbHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        return AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}", token="t", token_type=TokenType.PAT)

    def test_tables_parses_typed_columns(self):
        # snake_case wire shape; the transport camelCases keys before the facade parses.
        client = self._client({"tables": [{
            "name": "posts",
            "managed": False,
            "columns": [
                {"name": "id", "data_type": "uuid", "nullable": False},
                {"name": "title", "data_type": "text", "nullable": True},
            ],
        }]})
        tables = client.apps.raw_db.tables("app_x")
        self.assertEqual(_RawDbHandler.seen["path"], "/api/v1/apps/app_x/db/tables")
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].name, "posts")
        self.assertFalse(tables[0].managed)
        self.assertEqual(len(tables[0].columns), 2)
        self.assertEqual(tables[0].columns[0].data_type, "uuid")
        self.assertTrue(tables[0].columns[1].nullable)

    def test_tables_empty_means_genuinely_empty(self):
        # F-3: empty list + no exception = genuinely empty (raw DB off or 0 tables), not auth failure.
        client = self._client({"tables": []})
        tables = client.apps.raw_db.tables("app_x")
        self.assertEqual(tables, [])

    def test_table_rows_parses_page_and_forwards_per_page(self):
        client = self._client({"rows": [{"id": "1"}, {"id": "2"}], "page": 1, "per_page": 100, "has_more": True})
        page = client.apps.raw_db.table_rows("app_x", "posts", per_page=100)
        self.assertEqual(_RawDbHandler.seen["path"], "/api/v1/apps/app_x/db/tables/posts/rows")
        self.assertEqual(_RawDbHandler.seen["query"].get("per_page"), ["100"])
        self.assertEqual(len(page.rows), 2)
        self.assertEqual(page.page, 1)
        self.assertEqual(page.per_page, 100)
        self.assertTrue(page.has_more)

    def test_table_rows_forwards_page_when_set(self):
        client = self._client({"rows": [], "page": 3, "per_page": 25, "has_more": False})
        client.apps.raw_db.table_rows("app_x", "posts", per_page=25, page=3)
        self.assertEqual(_RawDbHandler.seen["query"].get("per_page"), ["25"])
        self.assertEqual(_RawDbHandler.seen["query"].get("page"), ["3"])

    def test_table_rows_omits_query_when_unset(self):
        client = self._client({"rows": [], "page": 1, "per_page": 50, "has_more": False})
        client.apps.raw_db.table_rows("app_x", "posts")
        self.assertEqual(_RawDbHandler.seen["query"], {})

    def test_requires_app_and_table_before_request(self):
        # Guards raise before any HTTP call, so an unroutable base_url never gets hit.
        client = AxHubClient(base_url="http://127.0.0.1:1", token="t", token_type=TokenType.PAT)
        with self.assertRaises(AxHubError):
            client.apps.raw_db.table_rows("app_x", "")
        with self.assertRaises(AxHubError):
            client.apps.raw_db.tables("")

    def test_async_raw_db_mirrors_sync(self):
        client = self._client({"tables": [{"name": "posts", "managed": True, "columns": []}]})
        async_client = AsyncAxHubClient(base_url=client.base_url, token="t", token_type=TokenType.PAT)
        tables = asyncio.run(async_client.apps.raw_db.tables("app_x"))
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].name, "posts")
        self.assertTrue(tables[0].managed)


if __name__ == "__main__":
    unittest.main()
