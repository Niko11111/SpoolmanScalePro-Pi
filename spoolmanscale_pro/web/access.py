"""Who may reach what: the checks every request passes before a route runs.

A new route is behind the login unless its endpoint is listed in
OPEN_ENDPOINTS, which is kept as short as the first visit allows.
"""

import logging

from flask import request, session

from .. import auth
from .responses import fail

log = logging.getLogger(__name__)

# What a visitor without a session may reach: the page shell, its files,
# and the routes that let them set a password or log in.
OPEN_ENDPOINTS = {
    "static",
    "pages.index",
    "api_auth.state",
    "api_auth.setup",
    "api_auth.login",
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def logged_in() -> bool:
    return auth.password_is_set() and session.get("gen") == auth.generation()


def guard():
    """Flask before_request. Returns a refusal, or None to let it through."""
    if request.method not in SAFE_METHODS:
        if not request.headers.get(auth.CSRF_HEADER):
            return fail("csrf", 403)
        if not auth.origin_matches(request.headers.get("Origin"), request.host):
            log.warning("Refused %s %s from origin %s", request.method, request.path,
                        request.headers.get("Origin"))
            return fail("csrf", 403)
    if request.endpoint in OPEN_ENDPOINTS:
        return None
    if not logged_in():
        return fail("login_required", 401)
    return None
