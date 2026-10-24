"""Entering this Pi as the server for every backend on the scale, so the
owner does not have to type three addresses on the device.

The scale keeps one address per backend, but POST /api/host sets the one of
the backend it uses right now. So, backend by backend: switch the scale to
it, wait until /status.json reports it (the scale applies a new mode on its
next loop pass), set the address, wait for the scale's own test. At the end
the scale goes back to the backend that runs on this Pi.

The scale visibly switches three times meanwhile, so this only runs when
the owner asks for it. Only the backend that runs here can pass the test;
for the others the address is stored and tested when they are switched to.
"""

import logging
import socket
import time
from dataclasses import dataclass
from typing import Callable

from . import settings
from .backends import BACKENDS, Backend, backend_by_key
from .jobs import JobFailed, Progress
from .scale_api import ScaleClient, ScaleError, own_address_towards

log = logging.getLogger(__name__)

MODE_CONFIRM_TIMEOUT_S = 30
HOST_TEST_TIMEOUT_S = 20
POLL_S = 1


@dataclass(frozen=True)
class Timing:
    """How this module waits; a test hands in one that does not."""
    sleep: Callable[[float], None]
    now: Callable[[], float]


REAL_TIMING = Timing(time.sleep, time.monotonic)


def own_host(scale_address: str, use_ip: bool) -> str:
    """How the scale should reach this Pi: its mDNS name (survives a new
    DHCP address; the scale resolves .local itself) or its IP address."""
    if use_ip:
        address = own_address_towards(scale_address)
        if address:
            return address
    return socket.gethostname().split(".")[0] + ".local"


def _wait_for_mode(client: ScaleClient, backend: Backend, timing: Timing) -> None:
    deadline = timing.now() + MODE_CONFIRM_TIMEOUT_S
    while client.status().get("backend") != backend.scale_name:
        if timing.now() > deadline:
            raise ScaleError("scale_mode_timeout", backend.key)
        timing.sleep(POLL_S)


def switch_scale(client: ScaleClient, backend: Backend, timing: Timing = REAL_TIMING) -> None:
    if client.status().get("backend") != backend.scale_name:
        client.set_mode(backend.scale_mode)
        _wait_for_mode(client, backend, timing)


def set_address(client: ScaleClient, address: str, timing: Timing = REAL_TIMING) -> dict:
    """Sets the address and returns the scale's test result: ok, and its
    message. tested False when the scale ran no test (its worker was busy)."""
    if not client.set_host(address).get("queued"):
        return {"tested": False, "ok": False, "msg": ""}
    deadline = timing.now() + HOST_TEST_TIMEOUT_S
    while timing.now() < deadline:
        result = client.host_test()
        if result.get("state") == "done":
            return {"tested": True, "ok": bool(result.get("ok")), "msg": str(result.get("msg", ""))}
        if result.get("state") == "idle":
            break
        timing.sleep(POLL_S)
    return {"tested": False, "ok": False, "msg": ""}


def configure(client: ScaleClient, host: str, return_to: Backend, progress: Progress,
              timing: Timing = REAL_TIMING) -> dict:
    results = {}
    for backend in BACKENDS:
        progress.step("scale_address")
        progress.set_result(current=backend.key)
        switch_scale(client, backend, timing)
        address = f"{host}:{backend.port}"
        results[backend.key] = {"address": address, **set_address(client, address, timing)}
        log.info("Scale address for %s set to %s (%s)", backend.key, address, results[backend.key])
    progress.step("switching_scale")
    switch_scale(client, return_to, timing)
    progress.set_result(current=None, addresses=results)
    return results


def run(use_ip: bool, progress: Progress) -> None:
    """The job behind the "Set up the scale" button."""
    current = settings.load()
    if not current["scale_address"]:
        raise JobFailed("scale_not_paired")
    client = ScaleClient(current["scale_address"], current["scale_password"])
    try:
        original = client.status().get("backend")
        active = backend_by_key(current["active_backend"] or "")
        back = active or next((b for b in BACKENDS if b.scale_name == original), BACKENDS[0])
        configure(client, own_host(current["scale_address"], use_ip), back, progress)
    except ScaleError as e:
        raise JobFailed(e.code, str(e)) from e
