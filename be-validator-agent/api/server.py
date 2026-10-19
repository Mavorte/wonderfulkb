"""Lokální HTTP server (stejné cesty jako mock). Dva režimy:

    FIXTURES=1 python3 server.py     # moto + fake S3 Vectors + data z mocku; API_KEY výchozí 'mock-key'
    python3 server.py                # skutečné AWS (profil z AWS_PROFILE), API klíč ze Secrets Manageru

V režimu fixtur navíc GET /v1/_mock/cases (index případů pro kontraktový test), stejně jako mock.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import core

API = None
INDEX = None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        u = urlparse(self.path)
        if INDEX is not None and u.path == "/v1/_mock/cases":
            if not API.keys.check(self.headers.get("x-api-key")):
                status, body = 403, {"error": "Chybí nebo je špatný API klíč"}
            else:
                status, body = 200, INDEX
        else:
            status, body = core.handle(self.command, u.path, parse_qs(u.query), dict(self.headers), api=API)
        if isinstance(body, core.Binary):
            raw, ctype, extra = body.data, body.content_type, body.headers
        else:
            raw, ctype, extra = core.dumps(body), "application/json; charset=utf-8", {}
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in extra.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_POST = do_PUT = do_DELETE = do_PATCH = do_GET

    def log_message(self, fmt, *args):  # řádek požadavku bez hlaviček; query se nevypisuje
        if os.environ.get("QUIET") != "1":
            sys.stderr.write("%s %s\n" % (self.command, urlparse(self.path).path))


def main():
    global API, INDEX
    if os.environ.get("FIXTURES") == "1":
        from moto import mock_aws
        import fixtures
        mock_aws().start()
        API, INDEX, _ = fixtures.build(os.environ.get("API_KEY", "mock-key"))
        mode = "fixtury (moto + fake S3 Vectors)"
    else:
        API = core.Api()
        mode = "skutečné AWS"
    port = int(os.environ.get("PORT", "8080"))
    print(f"Validator Agent API ({mode}) na :{port}{core.BASE}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
