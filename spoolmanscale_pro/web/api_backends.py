"""/api/backends and /api/job: which backend runs, switching, logs, and the
progress of whatever long operation is under way."""

from flask import Blueprint, request

from .. import backend_plan, backend_status, docker_compose, hardware, settings, switcher
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
        workers = plan["filaman_workers"]["in_use"]
        return fail(refusal, 409, budget=hardware.budget(plan["budget_ram_mb"], others, target.key, workers))
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


@bp.post("/backends/filaman/workers")
def set_filaman_workers():
    """Stores the choice (a number, or null for the automatic one). A running
    FilaMan is started again through compose, which recreates the container
    only if the number really changed; a stopped one takes it at its next
    start."""
    body = request.get_json(silent=True) or {}
    clean, refused = settings.clean_update({"filaman_workers": body.get("workers")})
    if refused:
        return fail("invalid_fields", fields=refused)
    if not backend_plan.situation()["filaman_workers"]["supported"]:
        return fail("workers_need_update", 409)
    if RUNNER.busy():
        return fail("busy", 409)
    settings.update(clean)
    if (docker_compose.states() or {}).get("filaman") != "running":
        return ok(restarting=False)
    job = RUNNER.start("workers", "filaman", lambda progress: switcher.restart(backend_by_key("filaman"), progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, restarting=True, job=job)


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
