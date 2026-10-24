"""/api/network: the Pi's name, its WLAN and its own hotspot.

Every change of the WLAN runs as a job: the browser usually loses the
connection while it happens, and the job finishes regardless.
"""

from flask import Blueprint, request

from .. import network
from .. import network_rules as rules
from ..jobs import RUNNER
from .responses import fail, ok

bp = Blueprint("api_network", __name__, url_prefix="/api/network")


def _start(kind: str, target: str, fn):
    job = RUNNER.start(kind, target, fn)
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("")
def overview():
    return ok(network={**network.status(), "ip": network.ip_status()})


@bp.post("/scan")
def scan():
    networks = network.scan()
    if networks is None:
        return fail("scan_failed", 503)
    return ok(networks=networks)


@bp.post("/wifi")
def join_wifi():
    body = request.get_json(silent=True) or {}
    ssid, psk = body.get("ssid"), body.get("psk", "")
    if not rules.valid_ssid(ssid):
        return fail("ssid_invalid")
    if not rules.valid_psk(psk, allow_empty=True):
        return fail("psk_invalid")
    return _start("wifi", ssid, lambda progress: network.join_wifi(ssid, psk, progress))


@bp.post("/hotspot")
def hotspot_on():
    body = request.get_json(silent=True) or {}
    ssid, psk, channel = body.get("ssid"), body.get("psk"), body.get("channel")
    if not rules.valid_ssid(ssid):
        return fail("ssid_invalid")
    if not rules.valid_psk(psk, allow_empty=False):
        return fail("psk_invalid")
    if not rules.valid_channel(channel):
        return fail("channel_invalid")
    return _start("hotspot_on", ssid, lambda progress: network.hotspot_on(ssid, psk, channel, progress))


@bp.post("/hotspot/off")
def hotspot_off():
    return _start("hotspot_off", "wlan0", network.hotspot_off)


@bp.post("/hostname")
def set_hostname():
    name = (request.get_json(silent=True) or {}).get("hostname")
    if not rules.valid_hostname(name):
        return fail("hostname_invalid")
    if not network.set_hostname(name):
        return fail("hostname_failed", 500)
    return ok(hostname=name)


@bp.post("/ip/check")
def check_address():
    address = (request.get_json(silent=True) or {}).get("address")
    if not isinstance(address, str):
        return fail("ip_invalid")
    return ok(verdict=network.check_address(address.strip()))


@bp.post("/ip/static")
def fix_address():
    """Fixes the given address (or, without one, the current) on the
    connection the Pi is in the network through."""
    address = (request.get_json(silent=True) or {}).get("address")
    if address is None:
        current = network.ip_status()
        address = current["address"].split("/")[0] if current and current["address"] else ""
    if not isinstance(address, str) or not address:
        return fail("ip_invalid")
    return _start("ip_static", address.strip(), lambda progress: network.fix_address(address.strip(), progress))


@bp.post("/ip/dhcp")
def address_from_router():
    return _start("ip_dhcp", "router", network.address_from_router)
