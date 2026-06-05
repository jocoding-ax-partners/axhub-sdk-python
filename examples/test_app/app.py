from __future__ import annotations
import json, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from axhub_sdk import AxHubClient, TokenType

if os.getenv("AXHUB_TOKEN"):
    c = AxHubClient(
        base_url=os.getenv("AXHUB_BASE_URL", "https://api.axhub.ai"),
        token=os.environ["AXHUB_TOKEN"],
        token_type=TokenType(os.environ["AXHUB_TOKEN_TYPE"]),
        default_tenant_id=os.getenv("AXHUB_TENANT_ID"),
    )
    got = c.identity.auth_get_api_v1_me()
    print(f"python prod test app ok {c.base_url} keys={len(got)}")
else:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = json.dumps({"id":"app_demo","tenant_id":"tnt_demo","slug":"demo","schema_name":"app_demo"}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler); threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        c = AxHubClient(base_url=f"http://127.0.0.1:{server.server_port}", token="pat_demo", token_type=TokenType.PAT, default_tenant_id="tnt_demo")
        got = c.apps.create({"slug":"demo","name":"Demo"}); print(f"python test app ok {got['id']} {c.base_url}")
    finally:
        server.shutdown()
