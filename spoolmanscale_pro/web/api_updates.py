"""/api/updates: newer versions of a backend, with release notes, and
installing one. Pre-releases are switched on through /api/settings
("include_prereleases")."""

from flask import Blueprint, request

from .. import backend_updates
from ..backends import backend_by_key
from ..jobs import RUNNER
from ..release_sources import SourceError
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
