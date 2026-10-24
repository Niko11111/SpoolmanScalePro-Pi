"""Looking for updates on its own: SpoolmanScale Pro itself and every
installed backend (its container exists), while settings "update_check" is
on. Nothing is ever installed from here.

A thread in the service wakes every WAKE_S and runs a round when the next
one is due: CHECK_EVERY_S after a round that reached GitHub, RETRY_S after
one that reached nothing (a Pi without internet). The first look comes
FIRST_LOOK_S after the start, and the time of the next round is kept on
disk, so restarting the service does not ask GitHub again.

A search on the Updates page goes through here as well. Each result is kept
with the version it was found for; once that changed (an update was
installed), the result is stale and no longer shown.

A round asks GitHub's API about once per item (release notes; GitHub allows
60 an hour per address without login) and ghcr.io two or three times per
backend. due(), fresh() and offer() are pure and tested in
tests/test_update_watch.py.
"""

import json
import logging
import os
import threading
import time

from . import app_update, backend_daily, backend_updates, docker_compose, settings
from .backends import BACKEND_KEYS, BACKENDS, Backend, backend_by_key
from .paths import UPDATE_CHECK_FILE
from .release_sources import SourceError
from .version import APP_VERSION

log = logging.getLogger(__name__)

CHECK_EVERY_S = 6 * 60 * 60
RETRY_S = 60 * 60
FIRST_LOOK_S = 5 * 60
WAKE_S = 10 * 60
# The key SpoolmanScale Pro itself is kept under, next to the backends'.
APP_KEY = "app"

_lock = threading.Lock()


def due(now: float, next_at: float | None, enabled: bool) -> bool:
    return enabled and (next_at is None or now >= next_at)


def fresh(item, current: str) -> bool:
    """Whether a kept result still speaks about the version running now."""
    return isinstance(item, dict) and item.get("current") == current and isinstance(item.get("result"), dict)


def offer(result: dict) -> dict | None:
    """What a kept result offers: a newer daily build, else the newest
    version; None when there is nothing to install."""
    if (result.get("daily") or {}).get("update"):
        return {"daily": True}
    if result.get("newer"):
        return {"version": result["newer"][0]}
    return None


def _load() -> dict:
    try:
        data = json.loads(UPDATE_CHECK_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"items": {}, "next_at": None}
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Update check file unreadable, starting afresh: %s", e)
        return {"items": {}, "next_at": None}
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return {"items": {}, "next_at": None}
    return data


def _save(data: dict) -> None:
    tmp = UPDATE_CHECK_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, UPDATE_CHECK_FILE)


def _keep(key: str, current: str, result: dict | None = None, error: str | None = None) -> None:
    """A result replaces the one kept; a failure only notes itself next to it."""
    with _lock:
        data = _load()
        item = data["items"].get(key) if fresh(data["items"].get(key), current) else None
        item = item or {"current": current}
        if result is not None:
            item.update(result=result, at=time.time(), error=None)
        else:
            item.update(error=error, failed_at=time.time())
        data["items"][key] = item
        _save(data)


def _current(key: str) -> str:
    return APP_VERSION if key == APP_KEY else backend_updates.current_version(backend_by_key(key))


def check_app() -> dict:
    """app_update.check(), kept. Raises SourceError."""
    try:
        result = app_update.check()
    except SourceError as e:
        _keep(APP_KEY, APP_VERSION, error=e.code)
        raise
    _keep(APP_KEY, APP_VERSION, result)
    return result


def check_backend(backend: Backend) -> dict:
    """What can be installed for a backend, kept. Raises SourceError."""
    current = backend_updates.current_version(backend)
    try:
        result = backend_daily.check(backend) if backend.daily_tag else backend_updates.check(backend)
    except SourceError as e:
        _keep(backend.key, current, error=e.code)
        raise
    _keep(backend.key, current, result)
    return result


def run_round() -> None:
    """Checks the app and every installed backend once."""
    states = docker_compose.states() or {}
    checks = [check_app] + [lambda b=b: check_backend(b) for b in BACKENDS
                            if states.get(b.key, "absent") != "absent"]
    reached = False
    for check in checks:
        try:
            check()
            reached = True
        except SourceError as e:
            log.info("Update check incomplete: %s", e)
    with _lock:
        data = _load()
        data["next_at"] = time.time() + (CHECK_EVERY_S if reached else RETRY_S)
        _save(data)


def known() -> dict:
    """The kept results that still apply, by key, with when they were found
    and the last failure since."""
    items = _load()["items"]
    return {key: items[key] for key in (APP_KEY, *BACKEND_KEYS) if fresh(items.get(key), _current(key))}


def summary() -> dict:
    """What the navigation and the tiles show: per key what it offers."""
    available = {key: found for key, item in known().items() if (found := offer(item["result"]))}
    return {"auto": settings.load()["update_check"], "available": available}


def _loop() -> None:
    time.sleep(FIRST_LOOK_S)
    while True:
        try:
            if due(time.time(), _load().get("next_at"), settings.load()["update_check"]):
                run_round()
        except Exception:  # outer boundary of the thread: log, and keep looking
            log.exception("Update check failed")
        time.sleep(WAKE_S)


def start_scheduler() -> None:
    threading.Thread(target=_loop, name="update-watch", daemon=True).start()
