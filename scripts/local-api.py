"""Run the Lambda locally behind a tiny HTTP server that mimics API Gateway.

    MODEL_ID=offline python3 scripts/local-api.py          # no AWS needed (deterministic summaries)
    MODEL_ID=apac.amazon.nova-micro-v1:0 python3 scripts/local-api.py   # real Bedrock with your AWS login

Then open demo/index.html?api=http://localhost:8787
"""
from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("MODEL_ID", "offline")

from incidentscribe.handler import lambda_handler  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def _event(self, method: str) -> dict:
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode() if length else None
        return {"version": "2.0", "rawPath": self.path.split("?")[0], "body": body, "isBase64Encoded": False,
                "requestContext": {"http": {"method": method, "path": self.path}}}

    def _send(self, resp: dict) -> None:
        self.send_response(resp["statusCode"])
        for k, v in resp.get("headers", {}).items():
            self.send_header(k, v)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()
        self.wfile.write(resp["body"].encode())

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send({"statusCode": 204, "body": ""})

    def do_GET(self) -> None:  # noqa: N802
        self._send(lambda_handler(self._event("GET")))

    def do_POST(self) -> None:  # noqa: N802
        self._send(lambda_handler(self._event("POST")))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    print(f"IncidentScribe local API on http://localhost:{port} (MODEL_ID={os.environ['MODEL_ID']})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
