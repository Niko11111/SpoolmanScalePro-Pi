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


def test_setup_then_logged_in_then_setup_closed(client):
    assert client.get("/api/auth/state").json["password_set"] is False
    assert client.post("/api/auth/setup", json={"password": "short"}, headers=H).status_code == 400
    assert client.post("/api/auth/setup", json={"password": "longenough"}, headers=H).json["ok"]
    assert client.get("/api/auth/state").json["logged_in"] is True
    r = client.post("/api/auth/setup", json={"password": "another one"}, headers=H)
    assert r.status_code == 409
    client.post("/api/auth/logout", headers=H)
    assert client.post("/api/auth/login", json={"password": "wrong pass"}, headers=H).status_code == 401
    assert client.post("/api/auth/login", json={"password": "longenough"}, headers=H).json["ok"]


def test_security_headers(client):
    r = client.get("/")
    assert "frame-ancestors 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


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
