"""/api/system: the Pi itself. Its vital signs, its clock, restart and
shutdown."""

import socket

from flask import Blueprint, request

from .. import demo, host_actions, os_update, system_info
from ..jobs import RUNNER
from ..version import APP_VERSION
from .responses import fail, ok

bp = Blueprint("api_system", __name__, url_prefix="/api/system")


@bp.get("")
def overview():
    return ok(version=APP_VERSION, hostname=socket.gethostname(), demo_enabled=demo.enabled(),
              **system_info.snapshot())


@bp.post("/clock")
def set_clock():
    epoch = (request.get_json(silent=True) or {}).get("epoch_s")
    if not host_actions.valid_epoch(epoch):
        return fail("invalid_time")
    if not host_actions.set_clock(epoch):
        return fail("clock_failed", 500)
    return ok(clock_epoch_s=epoch)


@bp.post("/reboot")
def reboot():
    # Not in the middle of a switch or a backup: that would leave a backend
    # half stopped or an archive half written.
    if RUNNER.busy():
        return fail("busy", 409)
    if not host_actions.reboot():
        return fail("reboot_failed", 500)
    return ok()


@bp.post("/poweroff")
def poweroff():
    if RUNNER.busy():
        return fail("busy", 409)
    if not host_actions.poweroff():
        return fail("poweroff_failed", 500)
    return ok()


def _start(kind: str, fn):
    job = RUNNER.start(kind, "pi", fn)
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("/os")
def os_state():
    return ok(upgrade_running=os_update.upgrade_running(), restart_needed=os_update.restart_needed())


@bp.post("/os/check")
def os_check():
    return _start("os_check", os_update.check)


@bp.post("/os/upgrade")
def os_upgrade():
    return _start("os_upgrade", os_update.upgrade)


@bp.post("/os/follow")
def os_follow():
    """Shows an upgrade that is running already, e.g. after the page or
    this service was restarted while it ran."""
    if not os_update.upgrade_running():
        return fail("os_upgrade_not_running", 409)
    return _start("os_upgrade", os_update.follow)
