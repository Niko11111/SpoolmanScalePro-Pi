"""/api/updates: newer versions of a backend or of SpoolmanScale Pro
itself, with release notes, and installing one. Pre-releases are switched
on through /api/settings ("include_prereleases")."""

from flask import Blueprint, request

from .. import app_update, backend_updates
from ..backends import backend_by_key
from ..jobs import RUNNER
from ..release_sources import SourceError
from ..version import APP_VERSION
from .responses import fail, ok

bp = Blueprint("api_updates", __name__, url_prefix="/api/updates")


@bp.get("/<key>")
def check(key):
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    try:
        return ok(update=backend_updates.check(backend))
    except SourceError as e:
        return fail(e.code, 503)


@bp.post("/<key>")
def install(key):
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    tag = (request.get_json(silent=True) or {}).get("version")
    if not isinstance(tag, str) or not tag:
        return fail("unknown_version")
    job = RUNNER.start("update", key, lambda progress: backend_updates.install(backend, tag, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("/app")
def app_overview():
    base = {"current": APP_VERSION, "previous": app_update.previous_release(),
            "prereleases": app_update.offers_prereleases()}
    try:
        return ok(app={**base, **app_update.check()})
    except SourceError as e:
        return ok(app={**base, "newer": [], "notes": [], "error": e.code})


@bp.post("/app")
def app_install():
    version = (request.get_json(silent=True) or {}).get("version")
    if not isinstance(version, str) or not app_update.VERSION_RE.match(version):
        return fail("unknown_version")
    if RUNNER.busy():
        return fail("busy", 409)
    outcome = app_update.start_update(version)
    if outcome == "failed":
        return fail("app_update_failed", 500)
    return ok(202, outcome=outcome)


@bp.get("/app/state")
def app_state():
    return ok(state=app_update.update_state(), version=APP_VERSION)


@bp.post("/app/rollback")
def app_rollback():
    if RUNNER.busy():
        return fail("busy", 409)
    if app_update.previous_release() is None:
        return fail("no_previous_release", 409)
    if not app_update.rollback():
        return fail("app_update_failed", 500)
    return ok(202)
