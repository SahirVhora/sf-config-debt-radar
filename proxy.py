#!/usr/bin/env python3
"""Minimal CORS proxy for SF Config Debt Radar browser app.
Run: python3 proxy.py [--port 5002]
In the browser app, keep Base URL as the real SF URL, for example:
https://api55.sapsf.eu/odata/v2
Then tick "Use local proxy". Do not paste the localhost proxy URL into Base URL.
"""

import http.server
import sys
import requests
from pathlib import Path
from urllib.parse import urlparse

PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--port" else 5002
APP_DIR = Path(__file__).resolve().parent

# Cap request bodies so a misbehaving client cannot make the proxy buffer
# arbitrarily large uploads. OData payloads are far smaller than this.
MAX_BODY_BYTES = 8 * 1024 * 1024

# Browser origins allowed to call the proxy. The app is served by this same
# server, so only our own origin qualifies; anything else gets 403 so a
# random webpage cannot relay requests through the local proxy.
_ALLOWED_ORIGINS = {
    f"http://localhost:{PORT}",
    f"http://127.0.0.1:{PORT}",
    f"http://[::1]:{PORT}",
}

# Only allow proxy requests to known SAP SuccessFactors API hosts
_ALLOWED_HOST_SUFFIXES = (
    ".sapsf.com",
    ".sapsf.eu",
    ".sapsf.cn",
    ".sapsf.us",
    ".successfactors.com",
    ".successfactors.eu",
)


def _is_allowed_proxy_target(url: str) -> bool:
    """Only proxy to known SAP SF API hosts to prevent open-proxy abuse."""
    try:
        hostname = urlparse(url).hostname or ""
        return hostname.endswith(_ALLOWED_HOST_SUFFIXES)
    except Exception:
        return False


class Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        origin = self.headers.get("Origin")
        if origin in _ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Authorization, Accept, Content-Type"
        )

    def _handle(self, method):
        origin = self.headers.get("Origin")
        if origin is not None and origin not in _ALLOWED_ORIGINS:
            self.send_error(403, "Origin not allowed")
            return

        if method == "GET" and self.path in ("/", "/index.html"):
            self._serve_app()
            return

        target = self.path.lstrip("/")
        if not target.startswith("https://"):
            self.send_error(400, "Path must be https://<sf-api-url>/...")
            return
        if not _is_allowed_proxy_target(target):
            self.send_error(403, "Target host is not an allowed SAP SF API endpoint")
            return

        data = None
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if content_length > MAX_BODY_BYTES:
            self.send_error(413, f"Request body too large. Max {MAX_BODY_BYTES} bytes")
            return
        if content_length > 0:
            data = self.rfile.read(content_length)

        forward_headers = {}
        for header in ("Authorization", "Accept", "Content-Type"):
            val = self.headers.get(header)
            if val:
                forward_headers[header] = val

        # Disable redirect following to prevent open-redirect SSRF chains when
        # the proxy target returns a 3xx. SF OData auth must never be forwarded
        # across a redirect hop.
        try:
            resp = requests.request(
                method=method,
                url=target,
                data=data,
                headers=forward_headers,
                timeout=60,
                allow_redirects=False,
            )
            body = resp.content
            self.send_response(resp.status_code)
            self._cors_headers()
            self.send_header(
                "Content-Type",
                resp.headers.get("Content-Type", "application/octet-stream"),
            )
            self.end_headers()
            self.wfile.write(body)
        except (requests.exceptions.RequestException, TimeoutError) as e:
            self.send_error(502, str(e))

    def _serve_app(self):
        body = (APP_DIR / "index.html").read_bytes()
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[proxy] {args[0]}")


if __name__ == "__main__":
    print(f"SF CORS proxy running on http://localhost:{PORT}")
    print("In the app, keep Base URL as: https://api55.sapsf.eu/odata/v2")
    print('Tick "Use local proxy" before Fetch metadata.')
    http.server.HTTPServer(("127.0.0.1", PORT), Proxy).serve_forever()
