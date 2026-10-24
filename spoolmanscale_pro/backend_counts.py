"""How many spools each ready backend holds, for its tile on the overview.

Asked in a thread of its own and kept for COUNT_TTL_S: the overview polls
every 5 s, and a backend that is slow to answer must not hold up the page.
A count that is not known yet, or that a backend would not give (FilaMan's
admin password changed, BamBuddy's login switched on), is None and the tile
shows none. A backend that stops is forgotten, so a restore or a new start
is counted afresh.

Active spools, archived ones left out, the way each backend counts them:
  Spoolman  GET /api/v1/spool?limit=1          header X-Total-Count
  FilaMan   GET /api/v1/spools?page_size=1     {"total": n}, as its admin
  BamBuddy  GET /api/v1/inventory/spools       a list, open without its login
The parsers are pure and tested in tests/test_backend_counts.py.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request

from . import backend_secrets, health
from .backends import Backend, backend_by_key
from .filaman_admin import FilamanAdmin, FilamanError

log = logging.getLogger(__name__)

COUNT_TTL_S = 60
COUNT_TIMEOUT_S = 3

_lock = threading.Lock()
_known: dict[str, tuple[float, int | None]] = {}
_asking: set[str] = set()


def parse_total_header(value) -> int | None:
    """Spoolman's X-Total-Count."""
    return int(value) if isinstance(value, str) and value.strip().isdigit() else None


def parse_list_length(body) -> int | None:
    """BamBuddy's spool list."""
    return len(body) if isinstance(body, list) else None


def stale(asked_at: float | None, now: float) -> bool:
    return asked_at is None or now - asked_at >= COUNT_TTL_S


def _get(url: str):
    with urllib.request.urlopen(url, timeout=COUNT_TIMEOUT_S) as r:
        return r.headers, r.read()


def _ask_spoolman(backend: Backend) -> int | None:
    headers, _ = _get(health.backend_url(backend) + "/api/v1/spool?limit=1")
    return parse_total_header(headers.get("X-Total-Count"))


def _ask_filaman(backend: Backend) -> int | None:
    login = backend_secrets.filaman_admin()
    admin = FilamanAdmin(health.backend_url(backend), timeout_s=COUNT_TIMEOUT_S)
    admin.login(login["email"], login["password"])
    try:
        return admin.count_spools()
    finally:
        admin.logout()


def _ask_bambuddy(backend: Backend) -> int | None:
    _, raw = _get(health.backend_url(backend) + "/api/v1/inventory/spools")
    return parse_list_length(json.loads(raw))


_ASK = {"spoolman": _ask_spoolman, "filaman": _ask_filaman, "bambuddy": _ask_bambuddy}


def _refresh(key: str) -> None:
    value = None
    try:
        value = _ASK[key](backend_by_key(key))
    except (urllib.error.URLError, OSError, ValueError, FilamanError) as e:
        log.info("Spool count of %s not available: %s", key, e)
    with _lock:
        _known[key] = (time.monotonic(), value)
        _asking.discard(key)


def known(ready: list[str]) -> dict[str, int | None]:
    """The counts known now for the ready backends. Starts asking where a
    count is missing or older than COUNT_TTL_S; the answer shows on a later
    poll."""
    now = time.monotonic()
    out = {}
    with _lock:
        for key in [k for k in _known if k not in ready]:
            del _known[key]
        for key in ready:
            asked_at, value = _known.get(key, (None, None))
            out[key] = value
            if stale(asked_at, now) and key not in _asking and key in _ASK:
                _asking.add(key)
                threading.Thread(target=_refresh, args=(key,), daemon=True).start()
    return out
