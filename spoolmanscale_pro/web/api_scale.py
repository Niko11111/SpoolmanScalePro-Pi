"""/api/scale and /api/settings: the paired scale and the service's settings."""

from flask import Blueprint, request

from .. import backend_plan, backend_secrets, scale_discovery, scale_keys, scale_setup, settings, switcher
from ..backends import backend_by_key
from ..jobs import RUNNER
from ..scale_api import ScaleClient, ScaleError, own_names, summarize
from ..ports import PROXY_PORT
from .responses import fail, ok

bp = Blueprint("api_scale", __name__, url_prefix="/api")


def _scale_view() -> dict:
    current = settings.load()
    address = current["scale_address"]
    if not address:
        return {"paired": False, "proxy_port": PROXY_PORT}
    try:
        status = ScaleClient(address, current["scale_password"]).status()
    except ScaleError as e:
        return {"paired": True, "address": address, "reachable": False, "error": e.code,
                "proxy_port": PROXY_PORT}
    active = backend_by_key(current["active_backend"] or "")
    return {"paired": True, "address": address, "proxy_port": PROXY_PORT,
            **summarize(status, active, own_names(address))}


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
    # A Pi Zero runs one backend at a time, whatever a request asks for.
    if clean.get("parallel_mode") and backend_plan.situation()["rules"]["parallel"] == "blocked":
        return fail("parallel_blocked", 409)
    return ok(settings=settings.public_view(settings.update(clean)))


@bp.post("/scale/discover")
def discover():
    """The scales announcing themselves on the network (mDNS)."""
    scales = scale_discovery.discover()
    if scales is None:
        return fail("discovery_unavailable", 503)
    return ok(scales=scales)


@bp.post("/scale/setup")
def setup_scale():
    """Enters this Pi as the server of every backend on the scale."""
    use_ip = (request.get_json(silent=True) or {}).get("use_ip") is True
    job = RUNNER.start("scale_setup", "scale", lambda progress: scale_setup.run(use_ip, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/scale/filaman")
def connect_filaman():
    """Registers the scale at FilaMan and gives it an API key. A login may
    come with the request when the stored one no longer works; it is used
    once and not kept."""
    body = request.get_json(silent=True) or {}
    email, password = body.get("email") or None, body.get("password") or None
    if (email is None) != (password is None):
        return fail("filaman_login_incomplete")
    job = RUNNER.start("scale_filaman", "filaman",
                       lambda progress: scale_keys.connect_filaman(email, password, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.post("/scale/bambuddy-key")
def bambuddy_key():
    key = (request.get_json(silent=True) or {}).get("key", "")
    if not isinstance(key, str) or (key and not 8 <= len(key) <= 200):
        return fail("bambuddy_key_invalid")
    if not settings.load()["scale_address"]:
        return fail("scale_not_paired", 409)
    try:
        scale_keys.send_bambuddy_key(key.strip())
    except ScaleError as e:
        return fail(e.code, 502)
    return ok()


@bp.get("/backends/filaman/login")
def filaman_login():
    """The FilaMan admin login this Pi made, to show its owner once asked."""
    return ok(login=backend_secrets.filaman_admin())
