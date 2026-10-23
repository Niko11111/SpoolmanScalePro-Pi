"""Switching the active backend, start to finish, as one job.

The order is the point of this module:
  1. stop every other backend (1 GB of RAM holds one of them),
  2. start the chosen one and wait until its health route answers,
  3. remember it as active, so it comes back after a reboot,
  4. tell the scale, and wait until the scale has reached it.

A scale that cannot be told is a warning, not a failure: the backend is up
and usable, and the page says what is wrong with the scale.

Nothing here runs at boot. The compose file says restart: unless-stopped,
so Docker brings back the backend that was running and leaves the stopped
ones stopped.
"""

from . import docker_compose, health, settings
from .backends import Backend
from .jobs import JobFailed, Progress
from .scale_api import ScaleClient, ScaleError, own_names, summarize, switch_and_confirm


def _stop_others(keep: str | None, progress: Progress) -> None:
    states = docker_compose.states()
    if states is None:
        raise JobFailed("docker_unavailable")
    running = [k for k, s in states.items() if s == "running" and k != keep]
    if running:
        progress.step("stopping_others")
    for key in running:
        if not docker_compose.stop(key).ok:
            raise JobFailed("stop_failed", key)


def _start(target: Backend, progress: Progress) -> None:
    progress.step("starting")
    if not docker_compose.up(target.key).ok:
        raise JobFailed("start_failed", target.key)
    progress.step("waiting_ready")
    if not health.wait_until_ready(target):
        raise JobFailed("not_ready", target.key)


def tell_scale(target: Backend, progress: Progress) -> None:
    current = settings.load()
    address = current["scale_address"]
    if not address:
        progress.set_result(scale="not_paired")
        return
    progress.step("switching_scale")
    client = ScaleClient(address, current["scale_password"])
    try:
        status = switch_and_confirm(client, target)
    except ScaleError as e:
        progress.warn(e.code)
        return
    summary = summarize(status, target, own_names(address))
    progress.set_result(scale=summary)
    if not (summary["on_active"] and summary["backend_ok"]):
        progress.warn("scale_not_confirmed")
    if not summary["points_here"]:
        progress.warn("scale_points_elsewhere")


def switch_to(target: Backend, progress: Progress) -> None:
    _stop_others(target.key, progress)
    _start(target, progress)
    settings.update({"active_backend": target.key})
    tell_scale(target, progress)


def stop_all(progress: Progress) -> None:
    _stop_others(None, progress)
    settings.update({"active_backend": None})
