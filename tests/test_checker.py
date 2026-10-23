"""Unit tests for checker.py using a throwaway local HTTP server."""
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from checker import check_service  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        code, body = (200, b"hello world") if self.path == "/ok" else (404, b"nope")
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def base_url():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_ok_status_and_text(base_url):
    r = check_service(base_url + "/ok", 200, "hello")
    assert r["ok"] and r["status_code"] == 200


def test_wrong_status(base_url):
    r = check_service(base_url + "/missing", 200)
    assert not r["ok"] and "unexpected status 404" in r["reason"]


def test_missing_text(base_url):
    r = check_service(base_url + "/ok", 200, "not-on-page")
    assert not r["ok"] and "expected text not found" in r["reason"]


def test_connection_refused():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # nothing listens on this port now
    r = check_service(f"http://127.0.0.1:{port}/", 200)
    assert not r["ok"] and "connection refused" in r["reason"]
