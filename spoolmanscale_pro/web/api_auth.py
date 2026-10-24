"""/api/auth: first visit, login, logout, changing or switching off the
account. The modes are explained in auth.py."""

from flask import Blueprint, request, session

from .. import auth
from .access import logged_in
from .responses import fail, ok

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


def _start_session() -> None:
    session.clear()
    session.permanent = True
    session["gen"] = auth.generation()


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _store_credentials(body: dict):
    """Checks and stores the user name and password of a request body.
    A refusal, or None once stored."""
    name = auth.clean_username(body.get("username"))
    if name is None:
        return fail("username_invalid")
    if not auth.password_acceptable(body.get("password")):
        return fail("password_too_short")
    auth.set_credentials(name, body["password"])
    _start_session()
    return None


def _current_password_ok(body: dict) -> bool:
    """In password mode a change needs the current password; in open mode
    there is none to give."""
    if auth.mode() == auth.MODE_OPEN:
        return True
    return auth.check_login(auth.username(), body.get("current")) == "ok"


@bp.get("/state")
def state():
    signed_in = logged_in()
    return ok(mode=auth.mode(), logged_in=signed_in,
              username=auth.username() if signed_in else "")


@bp.post("/setup")
def setup():
    # Only on the first visit. Afterwards a change needs the current password.
    if auth.mode() != auth.MODE_UNSET:
        return fail("account_already_set", 409)
    body = _body()
    if body.get("open") is True:
        auth.set_open()
        return ok()
    return _store_credentials(body) or ok()


@bp.post("/login")
def login():
    body = _body()
    verdict = auth.check_login(body.get("username"), body.get("password"))
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


@bp.post("/account")
def change_account():
    """New user name and password; also the way back from open mode."""
    body = _body()
    if not _current_password_ok(body):
        return fail("login_wrong", 401)
    return _store_credentials(body) or ok()


@bp.post("/open")
def switch_off_login():
    if not _current_password_ok(_body()):
        return fail("login_wrong", 401)
    auth.set_open()
    return ok()
