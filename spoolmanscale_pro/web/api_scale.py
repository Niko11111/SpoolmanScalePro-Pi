"""/api/scale and /api/settings: the paired scale and the service's settings."""

from flask import Blueprint, request

from .. import settings, switcher
from ..backends import backend_by_key
from ..jobs import RUNNER
from ..scale_api import ScaleClient, ScaleError, own_names, summarize
from .responses import fail, ok

bp = Blueprint("api_scale", __name__, url_prefix="/api")


def _scale_view() -> dict:
    current = settings.load()
    address = current["scale_address"]
    if not address:
        return {"paired": False}
    try:
        status = ScaleClient(address, current["scale_password"]).status()
    except ScaleError as e:
        return {"paired": True, "address": address, "reachable": False, "error": e.code}
    active = backend_by_key(current["active_backend"] or "")
    return {"paired": True, "address": address, **summarize(status, active, own_names(address))}


@bp.get("/scale")
def scale():
    return ok(scale=_scale_view())


@bp.post("/scale/sync")
def sync():
    """Points the scale at the active backend again, e.g. after it was
    switched by hand on the device."""
    active = backend_by_key(settings.load()["active_backend"] or "")
    if active is None:
        return fail("no_active_backend", 409)
    job = RUNNER.start("scale", active.key, lambda progress: switcher.tell_scale(active, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("/settings")
def get_settings():
    return ok(settings=settings.public_view(settings.load()))


@bp.post("/settings")
def save_settings():
    clean, refused = settings.clean_update(request.get_json(silent=True) or {})
    if refused:
        return fail("invalid_fields", fields=refused)
    return ok(settings=settings.public_view(settings.update(clean)))
