"""Talking to the local model, against a server that is not Ollama.

The point of these is the environment the application lands in rather than the
protocol: a corporate laptop with http_proxy set, a model that takes longer
than it is given, and something that is not a model answering on the port.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
from askbase.models import ModelClient, installed_models  # noqa: E402


def serve(handler_class):
    """A server on loopback, torn down with the test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class Ollamaish(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send({"models": [{"name": "sqlcoder:7b"}]})

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._send({"message": {"content": "```sql\nSELECT 1\n```"}})

    def _send(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class Sluggish(Ollamaish):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        time.sleep(2)
        super()._send({"message": {"content": "too late"}})


class NotAModel(Ollamaish):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = b"<html>Proxy authentication required</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def ollama():
    server, host = serve(Ollamaish)
    yield host
    server.shutdown()


def test_a_proxy_in_the_environment_is_ignored(monkeypatch, ollama):
    # On a work laptop http_proxy is set for the whole machine, and urllib
    # obeys it even for 127.0.0.1. The request then goes to the proxy, where
    # the offline guard refuses it, and the user is told that Ollama is not
    # running while it is running and listening.
    for var in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(var, "http://127.0.0.1:1")
    assert "SELECT 1" in ModelClient("sqlcoder:7b", host=ollama, timeout=5).complete("hi").text
    assert installed_models(host=ollama) == ["sqlcoder:7b"]


def test_a_model_that_runs_out_of_time_says_so(monkeypatch):
    # A read timeout is not a URLError, so it used to reach the window as an
    # unexpected error with a traceback. Waiting too long is the normal fate of
    # a large model on a laptop without a GPU.
    server, host = serve(Sluggish)
    try:
        with pytest.raises(RuntimeError) as e:
            ModelClient("sqlcoder:7b", host=host, timeout=0.3).complete("hi")
        assert "не ответила" in str(e.value)
    finally:
        server.shutdown()


def test_a_reply_that_is_not_json_says_so():
    # Something other than Ollama answering on 11434, a captive portal for
    # instance, used to come out as an unexpected error.
    server, host = serve(NotAModel)
    try:
        with pytest.raises(RuntimeError) as e:
            ModelClient("sqlcoder:7b", host=host, timeout=5).complete("hi")
        assert "не разобрался" in str(e.value)
    finally:
        server.shutdown()


def test_no_server_at_all_is_reported_as_ollama_not_running():
    client = ModelClient("sqlcoder:7b", host="http://127.0.0.1:1", timeout=2)
    with pytest.raises(RuntimeError) as e:
        client.complete("hi")
    assert "Ollama" in str(e.value)
    assert installed_models(host="http://127.0.0.1:1") == []
