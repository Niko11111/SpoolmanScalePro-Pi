"""The demo data set: one saved state per backend, and a reset to it.

Off unless paths.DEMO_FLAG_FILE exists on the Pi. There is no visible
switch on purpose: seven taps on the version in the page header ask whether
to turn it on or off (app.js), which lands in set_enabled(). By hand:
    sudo touch /var/lib/spoolmanscale-pro/demo-enabled

Set a backend up once the way the demo needs it (spools, the scale
registered in FilaMan, the BamBuddy API key on the scale), then save it as
the demo state. "Reset" puts every saved backend back to its demo state.

A reset restores files rather than replaying a seed through the APIs on
purpose: a seed would hand out new ids and lose FilaMan's device token and
BamBuddy's API key, and the scale would be cut off after every reset.

The demo states use the backup format (archive_format.py) and live in
paths.DEMO_SNAPSHOT_DIR, one file per backend, outside the backup list.
"""

import logging
from datetime import datetime
from pathlib import Path

from . import backups, settings, switcher
from .backends import BACKENDS, Backend, backend_by_key
from .jobs import Progress
from .paths import DEMO_FLAG_FILE, DEMO_SNAPSHOT_DIR

log = logging.getLogger(__name__)


def enabled() -> bool:
    return DEMO_FLAG_FILE.exists()


def set_enabled(on: bool) -> None:
    if on:
        DEMO_FLAG_FILE.touch()
    else:
        DEMO_FLAG_FILE.unlink(missing_ok=True)
    log.info("Demo mode %s", "on" if on else "off")


def snapshot_path(backend: Backend) -> Path:
    return DEMO_SNAPSHOT_DIR / f"{backend.key}.tar"


def status() -> list[dict]:
    rows = []
    for b in BACKENDS:
        path = snapshot_path(b)
        saved = None
        if path.is_file():
            saved = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        rows.append({"key": b.key, "label": b.label, "saved": saved})
    return rows


def save(backend: Backend, progress: Progress) -> None:
    with backups.backend_stopped(backend, progress):
        progress.step("archiving")
        backups.write_backup(backend, snapshot_path(backend))
    log.info("Demo state of %s saved", backend.key)


def _reset_order() -> list[Backend]:
    """The active backend first: it is the one the visitors are looking at."""
    active = backend_by_key(settings.load()["active_backend"] or "")
    saved = [b for b in BACKENDS if snapshot_path(b).is_file()]
    return sorted(saved, key=lambda b: b != active)


def reset(progress: Progress) -> None:
    order = _reset_order()
    if not order:
        progress.warn("demo_nothing_saved")
        return
    active = backend_by_key(settings.load()["active_backend"] or "")
    for backend in order:
        progress.set_result(current=backend.key)
        backups.restore(backend, snapshot_path(backend), progress, keep_safety=False)
    if active is not None and active in order:
        # The scale lost its server for the moment of the restart; this
        # waits until it has reached it again.
        switcher.tell_scale(active, progress)
    progress.set_result(current=None, reset=[b.key for b in order])
