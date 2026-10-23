"""The paired scale's web interface, served on this Pi at PROXY_PORT, so
one address is enough and the Pi's page can show the scale in a frame.

Why a port of its own and not a path like /scale/: the scale's pages use
absolute paths (/status.json, /app.css), which would miss under a prefix.
To the browser, <pi>:8081 and <pi> are the same site, so this Pi's login
cookie reaches the proxy and guards it: no session, no scale.

What is passed on and refused: proxy_rules.py. The forwarding uses
http.client rather than urllib so redirects reach the browser unchanged and
the answer streams through without being held in memory.
"""

import http.client
import logging

from flask import Flask, Response, current_app, request, stream_with_context

from . import auth, settings
from . import proxy_rules as rules
from .ports import PAGE_PORT, PROXY_PORT
from .web.access import logged_in

log = logging.getLogger(__name__)

# A firmware image is the largest thing the scale's pages upload.
MAX_BODY_BYTES = 16 * 1024 * 1024
# Flashing makes the scale answer late; everything else is quick.
SCALE_TIMEOUT_S = 120
CHUNK_BYTES = 64 * 1024
METHODS = ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"]

NOT_LOGGED_IN = ("Log in to SpoolmanScale Pro first, then reload this page.\n"
                 "Erst bei SpoolmanScale Pro anmelden, dann diese Seite neu laden.\n")


def _split(address: str) -> tuple[str, int]:
    host, _, port = address.partition(":")
    return host, int(port) if port.isdigit() else 80


def _forward(path: str, scale_address: str, scale_password: str) -> Response:
    host, port = _split(scale_address)
    target = "/" + path + (("?" + request.query_string.decode("latin-1")) if request.query_string else "")
    headers = rules.request_headers(dict(request.headers), scale_address, scale_password)
    body = request.get_data(cache=False) if request.method not in rules.SAFE_METHODS else None
    conn = http.client.HTTPConnection(host, port, timeout=SCALE_TIMEOUT_S)
    try:
        conn.request(request.method, target, body=body, headers=headers)
        upstream = conn.getresponse()
    except (OSError, http.client.HTTPException) as e:
        conn.close()
        log.warning("Scale proxy: %s %s failed: %s", request.method, target, e)
        return Response("The scale does not answer.\nDie Waage antwortet nicht.\n", 502, mimetype="text/plain")

    def stream():
        try:
            while chunk := upstream.read(CHUNK_BYTES):
                yield chunk
        finally:
            conn.close()

    frame_origin = rules.page_origin(request.host, current_app.config["PAGE_PORT"])
    return Response(stream_with_context(stream()), upstream.status,
                    headers=rules.response_headers(upstream.getheaders(), frame_origin))


def create_proxy_app(page_port: int = PAGE_PORT) -> Flask:
    """page_port: where this Pi's page is served, the one frame allowed."""
    app = Flask("spoolmanscale_pro_scale_proxy")
    # The same key and cookie name as the page, so its session counts here.
    app.secret_key = auth.session_key()
    app.config.update(SESSION_COOKIE_NAME="sspro_session", MAX_CONTENT_LENGTH=MAX_BODY_BYTES,
                      PAGE_PORT=page_port)

    @app.route("/", defaults={"path": ""}, methods=METHODS)
    @app.route("/<path:path>", methods=METHODS)
    def forward(path):
        if not logged_in():
            return Response(NOT_LOGGED_IN, 401, mimetype="text/plain")
        if not rules.origin_allowed(request.method, request.headers.get("Origin"),
                                    request.host, {current_app.config["PAGE_PORT"], PROXY_PORT}):
            log.warning("Scale proxy refused %s %s from origin %s", request.method, path,
                        request.headers.get("Origin"))
            return Response("Refused.\n", 403, mimetype="text/plain")
        current = settings.load()
        if not current["scale_address"]:
            return Response("No scale paired.\nKeine Waage gekoppelt.\n", 503, mimetype="text/plain")
        return _forward(path, current["scale_address"], current["scale_password"])

    return app
