"""What the page shows per backend: is its container there, running, ready,
how much RAM it uses, which version it runs, how many spools it holds, and
what this Pi allows (backend_plan.py).

describe() combines the registry, the container states, the health probe,
docker stats, the chosen versions and the spool counts (backend_counts.py).
merge() is the pure half of it and tested in tests/test_backend_status.py.
"""

import threading
import time

from . import backend_counts, backend_plan, backend_updates, docker_compose, health, settings, update_watch
from . import version_rules
from .backends import BACKENDS
from .jobs import RUNNER

# docker stats takes a second or two on a Pi 3; the overview polls every 5 s.
STATS_CACHE_S = 15
_stats = {"at": 0.0, "value": {}}
_stats_lock = threading.Lock()
# docker compose ps needs a quarter of a second just to load on a Pi 3.
STATES_CACHE_S = 15
_states = {"at": None, "job": None, "value": None}
_states_lock = threading.Lock()


def states_reusable(cached_at: float | None, now: float, job_then: tuple | None, job_now: tuple | None) -> bool:
    """A job is what changes a backend's state, so while one runs, or once one
    has started or ended since, the answer is asked for afresh. job_*: the
    job's (id, running), or None."""
    if cached_at is None or job_then != job_now or (job_now and job_now[1]):
        return False
    return now - cached_at < STATES_CACHE_S


def _job_marker() -> tuple | None:
    job = RUNNER.current()
    return (job["id"], job["running"]) if job else None


def _cached_states() -> dict[str, str] | None:
    marker = _job_marker()
    with _states_lock:
        if states_reusable(_states["at"], time.monotonic(), _states["job"], marker):
            return _states["value"]
    value = docker_compose.states()
    # Docker not answering is not kept: it should show as soon as it is back.
    with _states_lock:
        _states.update(at=time.monotonic() if value is not None else None, job=marker, value=value)
    return value


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
    "version" (as version_rules.display shows it), "spools" (None when
    not known; it only counts while the backend is ready) and "update"
    (update_watch.offer, None when there is none)."""
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
            "update": extra.get("update"),
        })
    return {"docker_ok": states is not None, "active": active, "backends": rows}


def describe() -> dict:
    states = _cached_states()
    ready = {b.key: health.is_ready(b) for b in BACKENDS
             if (states or {}).get(b.key) == "running"}
    running = [k for k, s in (states or {}).items() if s == "running"]
    counts = backend_counts.known([k for k, up in ready.items() if up])
    offers = update_watch.summary()["available"]
    details = {b.key: {"version": version_rules.display(backend_updates.current_version(b)),
                       "spools": counts.get(b.key), "update": offers.get(b.key)} for b in BACKENDS}
    view = merge(states, settings.load()["active_backend"], ready, _memory_use() if running else {}, details)
    view["plan"] = backend_plan.situation()
    return view
