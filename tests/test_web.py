"""The access rules, through Flask's test client: what a stranger, a
foreign page and a logged-in browser may do."""

import pytest

from spoolmanscale_pro.web import create_app
from spoolmanscale_pro.web.access import OPEN_ENDPOINTS

H = {"X-SSPro": "1"}


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with app.test_client() as c:
        yield c


def test_api_needs_a_login(client):
    r = client.get("/api/backends")
    assert r.status_code == 401 and r.json["error"] == "login_required"


def test_change_without_the_header_is_refused(client):
    r = client.post("/api/auth/setup", json={"password": "longenough"})
    assert r.status_code == 403 and r.json["error"] == "csrf"


def test_change_from_a_foreign_origin_is_refused(client):
    r = client.post("/api/auth/setup", json={"password": "longenough"},
                    headers={**H, "Origin": "http://evil.example"})
    assert r.status_code == 403


LOGIN = {"username": "admin", "password": "longenough"}


def test_setup_then_logged_in_then_setup_closed(client):
    assert client.get("/api/auth/state").json["mode"] == "unset"
    assert client.post("/api/auth/setup", json={"username": "admin", "password": "short"},
                       headers=H).status_code == 400
    assert client.post("/api/auth/setup", json={"username": " ", "password": "longenough"},
                       headers=H).json["error"] == "username_invalid"
    assert client.post("/api/auth/setup", json=LOGIN, headers=H).json["ok"]
    state = client.get("/api/auth/state").json
    assert state["mode"] == "password" and state["logged_in"] and state["username"] == "admin"
    r = client.post("/api/auth/setup", json={"open": True}, headers=H)
    assert r.status_code == 409
    client.post("/api/auth/logout", headers=H)
    assert client.get("/api/auth/state").json["username"] == ""
    wrong_name = {"username": "root", "password": "longenough"}
    assert client.post("/api/auth/login", json=wrong_name, headers=H).status_code == 401
    assert client.post("/api/auth/login", json=LOGIN, headers=H).json["ok"]


def test_open_mode_needs_the_password_and_lets_everyone_in(client):
    client.post("/api/auth/login", json=LOGIN, headers=H)
    assert client.post("/api/auth/open", json={"current": "wrong one"}, headers=H).status_code == 401
    assert client.post("/api/auth/open", json={"current": "longenough"}, headers=H).json["ok"]
    app = client.application
    with app.test_client() as stranger:
        assert stranger.get("/api/backends").status_code != 401
        # Still no requests from foreign pages, open or not.
        assert stranger.post("/api/auth/logout").status_code == 403
        # The way back needs no current password, there is none.
        assert stranger.post("/api/auth/account", json=LOGIN, headers=H).json["ok"]
    assert client.get("/api/auth/state").json["mode"] == "password"


def test_security_headers(client):
    r = client.get("/")
    assert "frame-ancestors 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-cache"


def test_open_endpoints_are_only_the_first_visit():
    assert OPEN_ENDPOINTS == {"static", "pages.index", "api_auth.state",
                              "api_auth.setup", "api_auth.login"}


def test_every_route_but_the_open_ones_refuses_a_stranger():
    app = create_app()
    with app.test_client() as stranger:
        for rule in app.url_map.iter_rules():
            if rule.endpoint in OPEN_ENDPOINTS:
                continue
            url = rule.rule.replace("<key>", "spoolman")
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                r = stranger.open(url, method=method, headers=H)
                assert r.status_code == 401, (method, url, r.status_code)


def test_demo_is_off_until_the_flag_file_exists(client):
    from spoolmanscale_pro.paths import DEMO_FLAG_FILE
    client.post("/api/auth/login", json=LOGIN, headers=H)
    DEMO_FLAG_FILE.unlink(missing_ok=True)
    assert client.get("/api/system").json["demo_enabled"] is False
    r = client.post("/api/demo/reset", headers=H)
    assert r.status_code == 409 and r.json["error"] == "demo_off"
    DEMO_FLAG_FILE.touch()
    try:
        assert client.get("/api/system").json["demo_enabled"] is True
        assert client.get("/api/demo").status_code == 200
    finally:
        DEMO_FLAG_FILE.unlink()


def test_network_input_is_checked_before_the_helper_runs(client, monkeypatch):
    from spoolmanscale_pro import host_actions
    called = []
    monkeypatch.setattr(host_actions.subprocess, "run", lambda *a, **k: called.append(a))
    client.post("/api/auth/login", json=LOGIN, headers=H)
    cases = [
        ("/api/network/hostname", {"hostname": "spoolmanscale_pro"}, "hostname_invalid"),
        ("/api/network/hostname", {"hostname": "x; reboot"}, "hostname_invalid"),
        ("/api/network/wifi", {"ssid": "", "psk": "longenough"}, "ssid_invalid"),
        ("/api/network/wifi", {"ssid": "Home", "psk": "short"}, "psk_invalid"),
        ("/api/network/hotspot", {"ssid": "Demo", "psk": "", "channel": 6}, "psk_invalid"),
        ("/api/network/hotspot", {"ssid": "Demo", "psk": "longenough", "channel": 5}, "channel_invalid"),
    ]
    for path, body, code in cases:
        r = client.post(path, json=body, headers=H)
        assert r.status_code == 400 and r.json["error"] == code, (path, body)
    assert called == []
