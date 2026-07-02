import json
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from axhub_sdk import AxHubClient, ROUTES, TokenType
from axhub_sdk.operations import OPERATION_METHODS

_ROUTE_BY_OPERATION = {route["operationId"]: route for route in ROUTES}
_PATH_PARAM_RE = re.compile(r"\{([^}]+)\}")


def _path_param_value(name: str) -> str:
    return {
        "tenantID": "tnt_1",
        "tenantSlug": "test-tenant",
        "appID": "app_1",
        "appSlug": "app-slug",
        "table": "table_1",
        "tableName": "table_1",
        "path": "resource-path",
        "domain": "example.com",
    }.get(name, f"{name.lower()}_1")


def _path_params_for(path: str) -> dict[str, str]:
    return {match.group(1): _path_param_value(match.group(1)) for match in _PATH_PARAM_RE.finditer(path)}


def _render_path(path: str, params: dict[str, str]) -> str:
    return _PATH_PARAM_RE.sub(lambda match: quote(params[match.group(1)], safe=""), path)


def _body_for(route: dict[str, str]):
    if route["method"] in {"GET", "DELETE"}:
        return None
    return {"operationId": route["operationId"], "ok": True}


class _OperationHandler(BaseHTTPRequestHandler):
    expected_index = 0
    failures: list[str] = []

    def log_message(self, *_args):
        return

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def _handle(self):
        if _OperationHandler.expected_index >= len(ROUTES):
            _OperationHandler.failures.append(f"unexpected extra request {self.command} {self.path}")
            self.send_response(500)
            self.end_headers()
            return
        route = ROUTES[_OperationHandler.expected_index]
        params = _path_params_for(route["path"])
        parsed = urlparse(self.path)
        want_path = _render_path(route["path"], params)
        if self.command != route["method"]:
            _OperationHandler.failures.append(f"{route['operationId']} method {self.command} != {route['method']}")
        if parsed.path != want_path:
            _OperationHandler.failures.append(f"{route['operationId']} path {parsed.path} != {want_path}")
        if parse_qs(parsed.query).get("e2e", [None])[0] != "ok":
            _OperationHandler.failures.append(f"{route['operationId']} missing e2e query")
        if self.headers.get("X-Api-Key") != "pat_e2e":
            _OperationHandler.failures.append(f"{route['operationId']} missing PAT header")
        if not self.headers.get("X-Request-ID"):
            _OperationHandler.failures.append(f"{route['operationId']} missing request id")
        content_length = int(self.headers.get("Content-Length") or "0")
        if content_length:
            self.rfile.read(content_length)
        _OperationHandler.expected_index += 1
        body = json.dumps({"operation_id": route["operationId"], "ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class AllOperationFacadesE2ETest(unittest.TestCase):
    def test_all_generated_operation_facades_make_http_requests(self):
        self.assertEqual(len(ROUTES), 85)
        self.assertEqual(len(OPERATION_METHODS), len(ROUTES))
        _OperationHandler.expected_index = 0
        _OperationHandler.failures = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OperationHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = AxHubClient(
                base_url=f"http://127.0.0.1:{server.server_address[1]}",
                token="pat_e2e",
                token_type=TokenType.PAT,
            )
            contexts = {
                "apps": client.apps,
                "identity": client.identity,
                "tenants": client.tenants,
                "authz": client.authz,
                "audit": client.audit,
                "gateway": client.gateway,
                "data": client.data,
                "deployments": client.deployments,
            }
            for item in OPERATION_METHODS:
                route = _ROUTE_BY_OPERATION[item["operationId"]]
                result = getattr(contexts[item["context"]], item["snake"])(
                    path_params=_path_params_for(route["path"]),
                    query={"e2e": "ok"},
                    body=_body_for(route),
                )
                self.assertEqual(result.get("operationId"), route["operationId"], result)
            self.assertEqual(_OperationHandler.expected_index, len(ROUTES))
            self.assertEqual(_OperationHandler.failures, [])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
