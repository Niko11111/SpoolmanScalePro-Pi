"""What the page shows per backend: is its container there, running, ready.

describe() combines the registry, the container states and the health
probe. merge() is the pure half of it and tested.
"""

from . import docker_compose, health, settings
from .backends import BACKENDS


def merge(states: dict[str, str] | None, active: str | None, ready: dict[str, bool]) -> dict:
    """states None means Docker did not answer, which the page shows as
    such rather than as "every backend stopped"."""
    rows = []
    for b in BACKENDS:
        state = (states or {}).get(b.key, "absent")
        rows.append({
            "key": b.key, "label": b.label, "port": b.port,
            "homepage": b.homepage, "state": state,
            "ready": ready.get(b.key, False), "active": b.key == active,
        })
    return {"docker_ok": states is not None, "active": active, "backends": rows}


def describe() -> dict:
    states = docker_compose.states()
    ready = {b.key: health.is_ready(b) for b in BACKENDS
             if (states or {}).get(b.key) == "running"}
    return merge(states, settings.load()["active_backend"], ready)
