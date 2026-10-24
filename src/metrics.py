"""Minimal Prometheus text-format exporter (standard library only)."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_lock = threading.Lock()
_up, _latency, _incidents, _attempts, _active = {}, {}, {}, {}, {}


def record_check(name, ok, latency_ms):
    with _lock:
        _up[name] = 1 if ok else 0
        if latency_ms is not None:
            _latency[name] = latency_ms
        for d in (_incidents, _attempts, _active):
            d.setdefault(name, 0)


def incident_opened(name):
    with _lock:
        _incidents[name] = _incidents.get(name, 0) + 1
        _active[name] = 1


def incident_resolved(name):
    with _lock:
        _active[name] = 0


def recovery_attempted(name):
    with _lock:
        _attempts[name] = _attempts.get(name, 0) + 1


def render():
    spec = [
        ("serviceguard_target_up", "gauge", "1 if the last check passed", _up),
        ("serviceguard_target_latency_ms", "gauge",
         "Latency of the last successful check in ms", _latency),
        ("serviceguard_incident_active", "gauge",
         "1 while an incident is open", _active),
        ("serviceguard_incidents_opened_total", "counter",
         "Incidents opened since ServiceGuard started", _incidents),
        ("serviceguard_recovery_attempts_total", "counter",
         "Recovery attempts since ServiceGuard started", _attempts),
    ]
    out = []
    with _lock:
        for name, kind, helptext, data in spec:
            out.append(f"# HELP {name} {helptext}")
            out.append(f"# TYPE {name} {kind}")
            for target, val in sorted(data.items()):
                out.append(f'{name}{{target="{target}"}} {val}')
    return "\n".join(out) + "\n"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = render().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_server(port=9101):
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
