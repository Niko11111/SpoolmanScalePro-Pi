"""/api/demo: the saved demo state per backend and the reset to it. Only
while demo mode is enabled on this Pi (demo.enabled())."""

from flask import Blueprint

from .. import demo
from ..backends import backend_by_key
from ..jobs import RUNNER
from .responses import fail, ok

bp = Blueprint("api_demo", __name__, url_prefix="/api/demo")


@bp.before_request
def demo_mode_on():
    if not demo.enabled():
        return fail("demo_off", 409)
    return None


@bp.get("")
def overview():
    return ok(snapshots=demo.status())


@bp.post("/<key>/save")
def save(key):
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    job = RUNNER.start("demo_save", key, lambda progress: demo.save(backend, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/reset")
def reset():
    job = RUNNER.start("demo_reset", "all", demo.reset)
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)
