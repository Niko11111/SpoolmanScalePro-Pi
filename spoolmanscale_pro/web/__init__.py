"""The Flask application: one blueprint per area, the access checks of
access.py before every request, and the security headers after it.

A new route goes into the blueprint of its area (api_<area>.py) and that
blueprint into BLUEPRINTS below.
"""

from datetime import timedelta

from flask import Flask, request

from .. import auth, paths
from . import (access, api_auth, api_backends, api_backup, api_demo, api_network, api_scale,
               api_system, api_updates, pages)
from .responses import fail

BLUEPRINTS = (pages, api_auth, api_backends, api_backup, api_demo, api_network, api_scale,
              api_system, api_updates)

SESSION_DAYS = 30
# The largest request body accepted. A backup upload is the only big one.
MAX_UPLOAD_BYTES = 512 * 1024 * 1024

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'self'; "
    # The scale's interface, served by scale_proxy.py on its own port.
    "frame-src 'self' http://*:8081; "
    "base-uri 'none'; form-action 'self'"
)


def _harden(response):
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.path == "/":
        # The shell names its scripts with ?v=<version>; it must be fetched
        # fresh, or after an update the browser keeps loading the old ones.
        response.headers["Cache-Control"] = "no-cache"
    return response


def create_app() -> Flask:
    paths.ensure_data_dirs()
    app = Flask(__name__, template_folder=str(paths.TEMPLATE_DIR),
                static_folder=str(paths.STATIC_DIR), static_url_path="/static")
    app.secret_key = auth.session_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="sspro_session",
        PERMANENT_SESSION_LIFETIME=timedelta(days=SESSION_DAYS),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    )
    for module in BLUEPRINTS:
        app.register_blueprint(module.bp)
    app.before_request(access.guard)
    app.after_request(_harden)
    app.register_error_handler(404, lambda e: fail("not_found", 404))
    app.register_error_handler(405, lambda e: fail("method_not_allowed", 405))
    app.register_error_handler(413, lambda e: fail("too_large", 413))
    return app
