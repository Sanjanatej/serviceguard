#!/usr/bin/env python3
"""Tiny test backend. Usage: backend.py PORT NAME"""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, NAME = int(sys.argv[1]), sys.argv[2]


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            code, body = 200, "OK\n"
        elif self.path == "/":
            code, body = 200, (f"ServiceGuard Test Site - "
                               f"served by backend {NAME} (port {PORT})\n")
        else:
            code, body = 404, "not found\n"
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
