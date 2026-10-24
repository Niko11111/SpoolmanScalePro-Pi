"""What the scale proxy (scale_proxy.py) passes on and what it refuses.
Pure functions, tested in tests/test_proxy_rules.py.

The proxy serves the scale's web interface on this Pi's own host, so the
Pi's page can show it in a frame and its login covers it. Four things
need care:
  - The scale only answers to its own names (Host header) and refuses a
    foreign Origin; the proxy sends its address as Host and no Origin.
  - Because the scale's own Origin check no longer sees the browser, the
    proxy does it: a changing request must come from this Pi's page or the
    proxy itself (same host name, one of their ports).
  - Hop-by-hop headers (RFC 9110 7.6.1) end at the proxy.
  - The scale forbids frames (X-Frame-Options: DENY) against clickjacking,
    except for its FilaMan or BamBuddy (firmware web/web_server.cpp). The
    proxy keeps that protection but names this Pi's page as the one
    allowed frame: frame-ancestors <page origin>.
"""

import base64
import urllib.parse

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailer", "transfer-encoding", "upgrade"}
# Request headers the scale's pages need; everything else (cookies of this
# Pi above all) stays here.
PASS_REQUEST = {"accept", "accept-language", "content-type", "range", "if-none-match",
                "if-modified-since", "authorization"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def origin_allowed(method: str, origin: str | None, host: str, ports: set[int]) -> bool:
    """host: the Host header the browser sent to the proxy (name:port).
    ports: the Pi page's port and the proxy's."""
    if method in SAFE_METHODS or not origin:
        return True
    expected = host.rsplit(":", 1)[0].lower()
    parts = urllib.parse.urlsplit(origin)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return (parts.hostname or "").lower() == expected and port in ports


def request_headers(incoming: dict, scale_address: str, scale_password: str) -> dict:
    """The headers sent to the scale. With a scale password given, the
    proxy logs in itself: this Pi's login already guards the proxy. Without
    one (also when the Pi has no login, scale_proxy.py), the browser's own
    Authorization goes through."""
    out = {k: v for k, v in incoming.items() if k.lower() in PASS_REQUEST}
    out["Host"] = scale_address
    if scale_password:
        token = base64.b64encode(f"spoolmanscale-pro:{scale_password}".encode()).decode()
        out = {k: v for k, v in out.items() if k.lower() != "authorization"}
        out["Authorization"] = f"Basic {token}"
    return out


# Replaced, not passed on: the scale's framing rules name its backend, the
# proxy's name this Pi's page.
FRAMING = {"x-frame-options", "content-security-policy"}


def page_origin(host: str, page_port: int) -> str:
    """The origin of this Pi's page, from the Host the proxy was asked at."""
    name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
    return f"http://{name}" if page_port == 80 else f"http://{name}:{page_port}"


def response_headers(incoming: list[tuple[str, str]], frame_origin: str) -> list[tuple[str, str]]:
    kept = [(k, v) for k, v in incoming
            if k.lower() not in HOP_BY_HOP and k.lower() != "content-length" and k.lower() not in FRAMING]
    return kept + [("Content-Security-Policy", f"frame-ancestors {frame_origin} 'self'")]
