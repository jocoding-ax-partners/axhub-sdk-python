import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from axhub_sdk import AxHubClient, AsyncAxHubClient, TokenType, AxHubError, ROUTES, ERROR_CODES, CONTEXT_ROUTES

class Handler(BaseHTTPRequestHandler):
    seen = {}
    def do_POST(self):
        Handler.seen = {"method": "POST", "path": self.path, "api_key": self.headers.get("X-Api-Key"), "request_id": self.headers.get("X-Request-ID")}
        body = {"id":"app_1","tenant_id":"tnt_1","slug":"my-app","schema_name":"app_my-app"}
        raw = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def log_message(self, *args): pass

class RegressionTest(unittest.TestCase):
    def test_apps_create_conformance(self):
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        client = AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}", token="pat_x", token_type=TokenType.PAT, default_tenant_id="tnt_1")
        got = client.apps.create({"slug":"my-app", "name":"My App"})
        self.assertEqual(got["id"], "app_1")
        self.assertEqual(got["schemaName"], "app_my-app")
        self.assertEqual(Handler.seen["path"], "/api/v1/tenants/tnt_1/apps")
        self.assertEqual(Handler.seen["api_key"], "pat_x")
        self.assertTrue(Handler.seen["request_id"])
    def test_tenant_required_before_request(self):
        client = AxHubClient(base_url="http://127.0.0.1:1", token="pat_x", token_type=TokenType.PAT)
        with self.assertRaises(AxHubError) as cm: client.apps.create({"slug":"my-app"})
        self.assertEqual((cm.exception.category, cm.exception.code), ("tenant_id_required", "tenant_id_required"))
    def test_route_and_error_coverage(self):
        self.assertEqual(len(ROUTES), 87)
        self.assertEqual(len(ERROR_CODES), 106)
        self.assertEqual(ERROR_CODES["slug_taken"].category, "conflict")
        for name in ["apps", "identity", "tenants", "authz", "audit", "gateway", "data", "deployments"]:
            self.assertIn(name, CONTEXT_ROUTES)
    def test_error_metadata_and_redaction(self):
        class ErrorHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw = json.dumps({"error":{"category":"unauthenticated","code":"token_expired","message":"expired","request_id":"req_py"}}).encode()
                self.send_response(401); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args): pass
        server = HTTPServer(("127.0.0.1", 0), ErrorHandler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start(); self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        client = AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}", token="pat_secret", token_type=TokenType.PAT)
        self.assertEqual(client.redacted_token(), "***REDACTED***")
        with self.assertRaises(AxHubError) as cm: client.request("appsGetApiV1AppsByAppID", path_params={"appID":"app_1"})
        self.assertEqual(cm.exception.request_id, "req_py")
        self.assertTrue(cm.exception.retryable)

    def test_scalar_json_error_body_becomes_typed_http_error(self):
        class ScalarErrorHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw = json.dumps("invalid_request").encode()
                self.send_response(400); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args): pass
        server = HTTPServer(("127.0.0.1", 0), ScalarErrorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        client = AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}", token="pat_secret", token_type=TokenType.PAT)
        with self.assertRaises(AxHubError) as cm:
            client.request("authGetWellKnownJwksJson")
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(cm.exception.code, "http_400")


    def test_non_json_success_body_is_returned_as_raw_payload(self):
        class HtmlHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw = b"<html>oauth redirect target</html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args): pass
        server = HTTPServer(("127.0.0.1", 0), HtmlHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        client = AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}")
        got = client.request("configGetConfigPublic")
        self.assertIn("oauth redirect target", got["raw"])

    def test_async_surface_exists(self):
        self.assertTrue(hasattr(AsyncAxHubClient, "apps"))

if __name__ == "__main__": unittest.main()
