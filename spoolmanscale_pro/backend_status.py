"""What the page shows per backend: is its container there, running, ready,
how much RAM it uses, which version it runs, how many spools it holds, and
what this Pi allows (backend_plan.py).

describe() combines the registry, the container states, the health probe,
docker stats, the chosen versions and the spool counts (backend_counts.py).
merge() is the pure half of it and tested in tests/test_backend_status.py.
"""

import threading
import time

from . import backend_counts, backend_plan, backend_updates, docker_compose, health, settings
from . import version_rules
from .backends import BACKENDS

# docker stats takes a second or two on a Pi 3; the overview polls every 5 s.
STATS_CACHE_S = 15
_stats = {"at": 0.0, "value": {}}
_stats_lock = threading.Lock()


def _memory_use() -> dict[str, int]:
    with _stats_lock:
        if time.monotonic() - _stats["at"] < STATS_CACHE_S:
            return _stats["value"]
    value = docker_compose.memory_use()
    with _stats_lock:
        _stats.update(at=time.monotonic(), value=value)
    return value


def merge(states: dict[str, str] | None, active: str | None, ready: dict[str, bool],
          ram: dict[str, int] | None = None, details: dict[str, dict] | None = None) -> dict:
    """states None means Docker did not answer, which the page shows as
    such rather than as "every backend stopped". details: per backend its
    "version" (as version_rules.display shows it) and "spools" (None when
    not known); the count only counts while the backend is ready."""
    rows = []
    for b in BACKENDS:
        state = (states or {}).get(b.key, "absent")
        is_ready = ready.get(b.key, False)
        extra = (details or {}).get(b.key, {})
        rows.append({
            "key": b.key, "label": b.label, "port": b.port,
            "homepage": b.homepage, "state": state,
            "ready": is_ready, "active": b.key == active,
            "ram_mb": (ram or {}).get(b.key) if state == "running" else None,
            "version": extra.get("version"),
            "spools": extra.get("spools") if is_ready else None,
        })
    return {"docker_ok": states is not None, "active": active, "backends": rows}


def describe() -> dict:
    states = docker_compose.states()
    ready = {b.key: health.is_ready(b) for b in BACKENDS
             if (states or {}).get(b.key) == "running"}
    running = [k for k, s in (states or {}).items() if s == "running"]
    counts = backend_counts.known([k for k, up in ready.items() if up])
    details = {b.key: {"version": version_rules.display(backend_updates.current_version(b)),
                       "spools": counts.get(b.key)} for b in BACKENDS}
    view = merge(states, settings.load()["active_backend"], ready, _memory_use() if running else {}, details)
    view["plan"] = backend_plan.situation()
    return view
