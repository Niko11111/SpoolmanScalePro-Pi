"""/api/auth: first password, login, logout, password change."""

from flask import Blueprint, request, session

from .. import auth
from .access import logged_in
from .responses import fail, ok

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


def _start_session() -> None:
    session.clear()
    session.permanent = True
    session["gen"] = auth.generation()


@bp.get("/state")
def state():
    return ok(password_set=auth.password_is_set(), logged_in=logged_in())


@bp.post("/setup")
def setup():
    # Only while there is no password. Afterwards a new one needs the old.
    if auth.password_is_set():
        return fail("password_already_set", 409)
    password = (request.get_json(silent=True) or {}).get("password")
    if not auth.password_acceptable(password):
        return fail("password_too_short")
    auth.set_password(password)
    _start_session()
    return ok()


@bp.post("/login")
def login():
    password = (request.get_json(silent=True) or {}).get("password")
    verdict = auth.check_login(password)
    if verdict == "wait":
        return fail("login_wait", 429)
    if verdict != "ok":
        return fail("login_wrong", 401)
    _start_session()
    return ok()


@bp.post("/logout")
def logout():
    session.clear()
    return ok()


@bp.post("/password")
def change_password():
    body = request.get_json(silent=True) or {}
    if auth.check_login(body.get("current")) != "ok":
        return fail("login_wrong", 401)
    if not auth.password_acceptable(body.get("new")):
        return fail("password_too_short")
    auth.set_password(body["new"])
    _start_session()
    return ok()
