"""/api/demo: the saved demo state per backend, the reset to it, and the
test inventory written into a backend. Only while demo mode is enabled on
this Pi (demo.enabled())."""

import logging

from flask import Blueprint

from .. import demo, inventory_import, inventory_writers
from ..backends import backend_by_key
from ..jobs import RUNNER
from .responses import fail, ok

log = logging.getLogger(__name__)

bp = Blueprint("api_demo", __name__, url_prefix="/api/demo")


@bp.before_request
def demo_mode_on():
    if not demo.enabled():
        return fail("demo_off", 409)
    return None


@bp.get("")
def overview():
    try:
        inventory = inventory_import.load()
        listed = {"spools": len(inventory["spools"]), "vendors": len(inventory["vendors"])}
    except inventory_import.InventoryError as e:
        log.warning("Test inventory not readable: %s", e)
        listed = None
    return ok(snapshots=demo.status(), inventory=listed)


@bp.post("/<key>/import")
def import_inventory(key):
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    job = RUNNER.start("demo_import", key, lambda progress: inventory_writers.write(backend, progress))
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


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
