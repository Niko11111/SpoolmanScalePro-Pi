"""/api/backends and /api/job: which backend runs, switching, logs, and the
progress of whatever long operation is under way."""

from flask import Blueprint, request

from .. import backend_plan, backend_status, docker_compose, hardware, switcher
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


@bp.post("/backends/<key>/start")
def start_one(key):
    """Starts a backend next to the running ones, where this Pi allows it."""
    target = backend_by_key(key)
    if target is None:
        return fail("unknown_backend", 404)
    states = docker_compose.states() or {}
    others = [k for k, s in states.items() if s == "running" and k != target.key]
    plan = backend_plan.situation()
    confirmed = (request.get_json(silent=True) or {}).get("confirm") is True
    refusal = backend_plan.start_refusal(plan["rules"], plan["parallel"], others, confirmed)
    if refusal:
        return fail(refusal, 409, budget=hardware.budget(plan["budget_ram_mb"], others, target.key))
    job = RUNNER.start("start", target.key, lambda progress: switcher.start_one(target, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/backends/<key>/stop")
def stop_one(key):
    target = backend_by_key(key)
    if target is None:
        return fail("unknown_backend", 404)
    job = RUNNER.start("stop_one", key, lambda progress: switcher.stop_one(target, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/backends/<key>/use")
def use_for_scale(key):
    """The scale uses this backend from now on; it is started if need be."""
    target = backend_by_key(key)
    if target is None:
        return fail("unknown_backend", 404)
    job = RUNNER.start("scale", key, lambda progress: switcher.use_for_scale(target, progress))
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
