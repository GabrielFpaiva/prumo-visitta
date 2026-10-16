import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class FakeStore:
    """Imita o R2 (GET/PUT por caminho) e o endpoint de callback, em 127.0.0.1."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.events: list[tuple[dict, str]] = []
        self.fail: dict[str, int] = {}
        store = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _should_fail(self):
                left = store.fail.get(self.path, 0)
                if left > 0:
                    store.fail[self.path] = left - 1
                    self.send_response(500)
                    self.end_headers()
                    return True
                return False

            def do_GET(self):
                if self._should_fail():
                    return
                body = store.objects.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_PUT(self):
                if self._should_fail():
                    return
                length = int(self.headers.get("Content-Length", 0))
                store.objects[self.path] = self.rfile.read(length)
                self.send_response(200)
                self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                store.events.append((json.loads(body), self.headers.get("X-Visitta-Signature", "")))
                store.objects.setdefault("/_raw_events", b"")
                store.objects["/_raw_events"] += body + b"\n"
                self.send_response(204)
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.server.server_port}{path}"

    def close(self):
        self.server.shutdown()


@pytest.fixture
def store():
    s = FakeStore()
    yield s
    s.close()
