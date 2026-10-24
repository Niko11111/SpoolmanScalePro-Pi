"""/api/updates: newer versions of a backend or of SpoolmanScale Pro
itself, with release notes, and installing one; a backend's daily build;
what the search on its own found (update_watch.py). Pre-releases and the
search on its own are switched through /api/settings ("include_prereleases",
"update_check")."""

import time

from flask import Blueprint, request

from .. import app_update, backend_daily, backend_updates, update_watch
from ..backends import backend_by_key
from ..jobs import RUNNER
from ..release_sources import SourceError
from ..version import APP_VERSION
from .responses import fail, ok

bp = Blueprint("api_updates", __name__, url_prefix="/api/updates")


@bp.get("/summary")
def summary():
    return ok(**update_watch.summary())


@bp.get("/known")
def known():
    return ok(items=update_watch.known())


@bp.get("/<key>")
def check(key):
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    try:
        return ok(update=update_watch.check_backend(backend), at=time.time())
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


@bp.post("/<key>/daily")
def install_daily(key):
    backend = backend_by_key(key)
    if backend is None or not backend.daily_tag:
        return fail("unknown_backend", 404)
    job = RUNNER.start("daily", key, lambda progress: backend_daily.install(backend, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/<key>/leave-daily")
def leave_daily(key):
    backend = backend_by_key(key)
    if backend is None or not backend.daily_tag:
        return fail("unknown_backend", 404)
    job = RUNNER.start("leave_daily", key, lambda progress: backend_daily.leave(backend, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("/app")
def app_overview():
    base = {"current": APP_VERSION, "previous": app_update.previous_release(),
            "prereleases": app_update.offers_prereleases()}
    try:
        return ok(app={**base, **update_watch.check_app(), "at": time.time()})
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
