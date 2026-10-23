"""/api/backends and /api/job: which backend runs, switching, logs, and the
progress of whatever long operation is under way."""

from flask import Blueprint

from .. import backend_status, docker_compose, switcher
from ..backends import backend_by_key
from ..jobs import RUNNER
from .responses import fail, ok

bp = Blueprint("api_backends", __name__, url_prefix="/api")


@bp.get("/backends")
def overview():
    return ok(**backend_status.describe())


@bp.post("/backends/<key>/activate")
def activate(key):
    target = backend_by_key(key)
    if target is None:
        return fail("unknown_backend", 404)
    job = RUNNER.start("switch", key, lambda progress: switcher.switch_to(target, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/backends/stop")
def stop_all():
    job = RUNNER.start("stop", "all", switcher.stop_all)
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("/backends/<key>/logs")
def logs(key):
    if backend_by_key(key) is None:
        return fail("unknown_backend", 404)
    result = docker_compose.logs(key)
    if not result.ok:
        return fail("docker_unavailable", 503)
    return ok(lines=result.output.splitlines())


@bp.get("/job")
def job():
    return ok(job=RUNNER.current())
