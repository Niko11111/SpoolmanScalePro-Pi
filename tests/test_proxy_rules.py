from spoolmanscale_pro import proxy_rules as pr

PORTS = {80, 8081}


def test_origin_rules():
    assert pr.origin_allowed("GET", "http://evil.example", "pi.local:8081", PORTS)
    assert pr.origin_allowed("POST", None, "pi.local:8081", PORTS)
    assert pr.origin_allowed("POST", "http://pi.local:8081", "pi.local:8081", PORTS)
    assert pr.origin_allowed("POST", "http://pi.local", "pi.local:8081", PORTS)
    assert not pr.origin_allowed("POST", "http://evil.example", "pi.local:8081", PORTS)
    # Same host, but Spoolman's port: another application, not this Pi's page.
    assert not pr.origin_allowed("POST", "http://pi.local:7912", "pi.local:8081", PORTS)
    assert not pr.origin_allowed("POST", "null", "pi.local:8081", PORTS)


def test_request_headers_drop_cookies_and_set_host():
    out = pr.request_headers({"Cookie": "sspro_session=x", "Accept": "*/*", "Origin": "http://pi.local",
                              "Content-Type": "text/plain"}, "192.168.4.37", "")
    assert out == {"Accept": "*/*", "Content-Type": "text/plain", "Host": "192.168.4.37"}


def test_scale_password_replaces_any_authorization():
    out = pr.request_headers({"Authorization": "Basic Zm9vOmJhcg=="}, "scale.local", "1234")
    assert out["Authorization"] == "Basic c3Bvb2xtYW5zY2FsZS1wcm86MTIzNA=="


def test_response_headers_drop_hop_by_hop_and_name_the_page_as_the_only_frame():
    out = pr.response_headers([("Content-Type", "text/html"), ("Connection", "close"),
                               ("Transfer-Encoding", "chunked"), ("Content-Length", "9"),
                               ("X-Frame-Options", "DENY"),
                               ("Content-Security-Policy", "frame-ancestors http://filaman:8002")],
                              "http://pi.local")
    assert out == [("Content-Type", "text/html"),
                   ("Content-Security-Policy", "frame-ancestors http://pi.local 'self'")]


def test_page_origin():
    assert pr.page_origin("pi.local:8081", 80) == "http://pi.local"
    assert pr.page_origin("localhost:8081", 8090) == "http://localhost:8090"
