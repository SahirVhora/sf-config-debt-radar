#!/usr/bin/env python3
"""Minimal CORS proxy for SF Config Debt Radar browser app.
Run: python3 proxy.py [--port 5002]
In the browser app, keep Base URL as the real SF URL, for example:
https://api55.sapsf.eu/odata/v2
Then tick "Use local proxy". Do not paste the localhost proxy URL into Base URL.
"""
import http.server
import urllib.request
import urllib.error
import ssl
import sys
import base64
from pathlib import Path

PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 5002
APP_DIR = Path(__file__).resolve().parent


class Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Accept, Content-Type')

    def _handle(self, method):
        if method == 'GET' and self.path in ('/', '/index.html'):
            self._serve_app()
            return

        target = self.path.lstrip('/')
        if not target.startswith('https://'):
            self.send_error(400, 'Path must be https://<sf-api-url>/...')
            return

        data = None
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            data = self.rfile.read(content_length)

        req = urllib.request.Request(target, data=data, method=method)

        for header in ('Authorization', 'Accept', 'Content-Type'):
            val = self.headers.get(header)
            if val:
                req.add_header(header, val)

        ctx = ssl.create_default_context()
        try:
            resp = urllib.request.urlopen(req, timeout=60, context=ctx)
            body = resp.read()
            self.send_response(resp.status)
            self._cors_headers()
            self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/octet-stream'))
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(502, str(e))

    def _serve_app(self):
        body = (APP_DIR / 'index.html').read_bytes()
        self.send_response(200)
        self._cors_headers()
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[proxy] {args[0]}")


if __name__ == '__main__':
    print(f"SF CORS proxy running on http://localhost:{PORT}")
    print("In the app, keep Base URL as: https://api55.sapsf.eu/odata/v2")
    print('Tick "Use local proxy" before Fetch metadata.')
    http.server.HTTPServer(('127.0.0.1', PORT), Proxy).serve_forever()
