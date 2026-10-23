"""The proxy against a small HTTP server standing in for the scale: what
reaches the scale, and who gets through."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from spoolmanscale_pro import auth, settings
from spoolmanscale_pro.paths import AUTH_FILE
from spoolmanscale_pro.scale_proxy import create_proxy_app

SEEN = []


class FakeScale(BaseHTTPRequestHandler):
    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        SEEN.append({"method": self.command, "path": self.path, "headers": dict(self.headers),
                     "body": self.rfile.read(length).decode()})
        payload = json.dumps({"backend": "Spoolman"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = _answer

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def scale():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeScale)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def proxy(scale):
    # The tests share one data directory; whatever this sets up, it removes,
    # so a later test still sees a first visit.
    made_login = auth.mode() == auth.MODE_UNSET
    if made_login:
        auth.set_credentials("admin", "longenough")
    settings.update({"scale_address": scale, "scale_password": "1234"})
    app = create_proxy_app()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s["gen"] = auth.generation()
        yield c
    settings.update({"scale_address": "", "scale_password": ""})
    if made_login:
        AUTH_FILE.unlink()


def test_a_stranger_gets_no_scale(scale):
    SEEN.clear()
    with create_proxy_app().test_client() as stranger:
        assert stranger.get("/status.json").status_code == 401
    assert SEEN == []


def test_what_reaches_the_scale(proxy, scale):
    SEEN.clear()
    r = proxy.post("/api/backend/mode?x=1", data="2", headers={
        "Origin": "http://localhost", "Content-Type": "text/plain", "Host": "localhost:8081"})
    assert r.status_code == 200 and r.json == {"backend": "Spoolman"}
    got = SEEN[0]
    assert got["path"] == "/api/backend/mode?x=1" and got["body"] == "2"
    assert got["headers"]["Host"] == scale
    assert "Origin" not in got["headers"] and "Cookie" not in got["headers"]
    assert got["headers"]["Authorization"].startswith("Basic ")


def test_a_foreign_origin_is_refused_before_the_scale(proxy):
    SEEN.clear()
    r = proxy.post("/api/backend/mode", data="2", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403 and SEEN == []
