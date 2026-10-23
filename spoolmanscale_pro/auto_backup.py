"""The daily backup of the active backend.

A thread in the service looks once a minute whether it is time: the hour
set on the Backup page has come and today has no automatic backup yet.
Then it starts an ordinary backup job (reason "auto"); if another job is
running, the next minute tries again. The day of the last run is kept in
the settings, so a restart of the service does not make a second one.

due() is pure and tested.
"""

import logging
import threading
import time
from datetime import datetime

from . import backups, docker_compose, settings
from .backends import backend_by_key
from .jobs import RUNNER

log = logging.getLogger(__name__)

CHECK_INTERVAL_S = 60


def due(now: datetime, enabled: bool, hour: int, last_day: str) -> bool:
    return enabled and now.hour >= hour and last_day != now.date().isoformat()


def tick(now: datetime) -> bool:
    """Starts today's backup when it is due. True when it was started."""
    current = settings.load()
    if not due(now, current["auto_backup"], current["auto_backup_hour"], current["auto_backup_last"]):
        return False
    backend = backend_by_key(current["active_backend"] or "")
    if backend is None or (docker_compose.states() or {}).get(backend.key) != "running":
        return False  # nothing runs that could change; tried again tomorrow at the latest
    job = RUNNER.start("backup", backend.key, lambda progress: backups.create(backend, progress, reason="auto"))
    if job is None:
        return False
    settings.update({"auto_backup_last": now.date().isoformat()})
    log.info("Daily backup of %s started", backend.key)
    return True


def _loop() -> None:
    while True:
        time.sleep(CHECK_INTERVAL_S)
        try:
            tick(datetime.now())
        except Exception:  # outer boundary of the thread: log, and keep looking
            log.exception("Daily backup check failed")


def start_scheduler() -> None:
    threading.Thread(target=_loop, name="auto-backup", daemon=True).start()
