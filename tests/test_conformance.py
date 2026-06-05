import json, os, threading, unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from axhub_sdk import AxHubClient, AxHubError

class VectorHandler(BaseHTTPRequestHandler):
    vector = None; seen = {}
    def do_POST(self): self._handle()
    def do_GET(self): self._handle()
    def do_PATCH(self): self._handle()
    def do_DELETE(self): self._handle()
    def _handle(self):
        VectorHandler.seen = {"method": self.command, "path": self.path.split("?", 1)[0], "headers": {k.lower(): v for k, v in self.headers.items()}}
        response = VectorHandler.vector.get("mockResponse") or {"status": 200, "body": {}}
        raw = json.dumps(response.get("body") or {}).encode(); self.send_response(response.get("status") or 200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def log_message(self, *args): pass

class ConformanceTest(unittest.TestCase):
    def test_vectors(self):
        vectors = self._vectors()
        self.assertTrue(vectors)
        for path in vectors:
            with self.subTest(path=path.name):
                v = json.loads(path.read_text()); VectorHandler.vector = v; VectorHandler.seen = {}
                server = HTTPServer(("127.0.0.1", 0), VectorHandler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                c = AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}", token=v.get("client", {}).get("token"), token_type=v.get("client", {}).get("tokenType"), default_tenant_id=v.get("client", {}).get("defaultTenantId"), default_tenant_slug=v.get("client", {}).get("defaultTenantSlug"))
                try:
                    try:
                        got = self._dispatch(c, v)
                        self.assertIn("ok", v["expect"])
                        for k,want in v["expect"]["ok"].items(): self.assertEqual(got.get(k), want)
                    except AxHubError as e:
                        self.assertIn("error", v["expect"]); want = v["expect"]["error"]
                        self.assertEqual((e.category,e.code), (want["category"], want["code"]))
                        if "requestId" in want: self.assertEqual(e.request_id, want["requestId"])
                        if "retryable" in want: self.assertEqual(e.retryable, want["retryable"])
                    if v.get("httpExpect"):
                        self.assertEqual(VectorHandler.seen["method"], v["httpExpect"]["method"]); self.assertEqual(VectorHandler.seen["path"], v["httpExpect"]["path"])
                        for h in v["httpExpect"].get("headersInclude", []): self.assertTrue(VectorHandler.seen["headers"].get(h), h)
                        for h,want in v["httpExpect"].get("headersExact", {}).items(): self.assertEqual(VectorHandler.seen["headers"].get(h), want)
                    else:
                        self.assertEqual(VectorHandler.seen, {})
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=2)

    def _dispatch(self, c, v):
        call = v["call"]
        if call["symbol"] == "sdk.apps.create": return c.apps.create(call.get("args") or {})
        if call["symbol"] == "sdk.operation":
            ctx = getattr(c, call["context"])
            return getattr(ctx, call["method"])(path_params=call.get("pathParams") or {}, query=call.get("query") or {}, body=call.get("body"))
        if call["symbol"] == "sdk.redactedToken": return {"redactedToken": c.redacted_token()}
        raise AssertionError(f"unknown vector symbol {call['symbol']}")

    def _vectors(self):
        candidates = []
        if os.environ.get("AXHUB_CONFORMANCE_DIR"): candidates.append(Path(os.environ["AXHUB_CONFORMANCE_DIR"]))
        candidates.append(Path("testdata/conformance/vectors"))
        candidates.append(Path("../conformance/vectors"))
        candidates.append(Path(os.environ.get("AXHUB_SPEC_DIR", "../../axhub-sdk-spec"))/"conformance/vectors")
        for d in candidates:
            vectors = sorted(d.glob("*.json"))
            if vectors: return vectors
        return []

if __name__ == "__main__": unittest.main()
