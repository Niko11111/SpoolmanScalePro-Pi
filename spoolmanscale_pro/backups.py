"""Backing up and restoring one backend's data, as jobs.

A backup stops the backend if it runs (a database must not be copied
mid-write), packs its volume, and starts it again. A restore first saves the
current data as a "before-restore" backup, then replaces the volume; if
that fails, the saved data go back in. Either way the backend ends in the
state it was in before: running and answering, or stopped.

File format and name rules: archive_format.py. Where the files live:
paths.BACKUP_DIR, newest BACKUPS_KEPT per backend.
"""

import logging
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import archive_format, docker_compose, health
from .archive_format import ArchiveError
from .backends import Backend
from .jobs import JobFailed, Progress
from .paths import BACKUP_DIR
from .version import APP_VERSION

log = logging.getLogger(__name__)

BACKUPS_KEPT = 10
# Below this, a backup is not started: a full SD card stops the backends too.
MIN_FREE_BYTES = 300 * 1024 * 1024


def _start_again(backend: Backend, progress: Progress) -> str | None:
    """Starts the backend and waits for it. The failure code, or None."""
    progress.step("starting")
    if not docker_compose.up(backend.key).ok:
        return "start_failed"
    progress.step("waiting_ready")
    if not health.wait_until_ready(backend):
        return "not_ready"
    return None


@contextmanager
def backend_stopped(backend: Backend, progress: Progress):
    """Stops the backend for the duration of the block if it runs, and
    starts it again afterwards, also when the block failed. A failed restart
    is the job's error only if the block itself went through; otherwise the
    block's error is the one reported and the restart failure is logged."""
    states = docker_compose.states()
    if states is None:
        raise JobFailed("docker_unavailable")
    was_running = states.get(backend.key) == "running"
    if was_running:
        progress.step("stopping")
        if not docker_compose.stop(backend.key).ok:
            raise JobFailed("stop_failed", backend.key)
    completed = False
    try:
        yield
        completed = True
    finally:
        error = _start_again(backend, progress) if was_running else None
        if error and completed:
            raise JobFailed(error, backend.key)
        if error:
            log.error("%s did not come back after a failed operation: %s", backend.key, error)


def _check_space(directory: Path) -> None:
    if shutil.disk_usage(directory).free < MIN_FREE_BYTES:
        raise JobFailed("disk_full")


def write_backup(backend: Backend, dest: Path) -> None:
    """Packs the (stopped) backend's volume into a bundle at dest."""
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        data = Path(tmp) / archive_format.DATA_NAME
        if not docker_compose.archive_volume(backend.key, backend.data_dir,
                                             backend.archive_skip, data).ok:
            raise JobFailed("archive_failed", backend.key)
        meta = archive_format.make_meta(backend.key, docker_compose.image_of(backend.key),
                                        APP_VERSION, datetime.now())
        partial = dest.with_suffix(".partial")
        archive_format.write_bundle(partial, meta, data)
        partial.replace(dest)
    log.info("Backup of %s written to %s", backend.key, dest.name)


def _prune(key: str) -> None:
    mine = sorted((p for p in BACKUP_DIR.glob(f"{key}_*.tar")), key=lambda p: p.name, reverse=True)
    for old in mine[BACKUPS_KEPT:]:
        old.unlink(missing_ok=True)
        log.info("Old backup removed: %s", old.name)


def create(backend: Backend, progress: Progress) -> None:
    _check_space(BACKUP_DIR)
    dest = BACKUP_DIR / archive_format.backup_name(backend.key, datetime.now())
    with backend_stopped(backend, progress):
        progress.step("archiving")
        write_backup(backend, dest)
    _prune(backend.key)
    progress.set_result(name=dest.name)


def check_bundle(backend: Backend, bundle: Path, work_dir: Path) -> tuple[Path, dict]:
    """Reads and checks a bundle for this backend. Returns the extracted
    data archive and the meta, or raises JobFailed with the archive's code."""
    try:
        meta = archive_format.read_meta(bundle)
        if meta["backend"] != backend.key:
            raise ArchiveError("archive_other_backend", meta["backend"])
        data = work_dir / archive_format.DATA_NAME
        archive_format.extract_data(bundle, data)
        archive_format.check_data_archive(data)
    except ArchiveError as e:
        raise JobFailed(e.code, e.detail) from e
    return data, meta


def _put_back(backend: Backend, safety: Path, work_dir: Path) -> None:
    """After a failed restore: the data from before go back in."""
    data = work_dir / "safety.tar.gz"
    archive_format.extract_data(safety, data)
    if docker_compose.restore_volume(backend.key, backend.data_dir, backend.archive_skip, data).ok:
        log.warning("Restore of %s failed; the previous data are back", backend.key)
    else:
        log.error("Restore of %s failed and putting back %s failed too", backend.key, safety.name)


def _replace_data(backend: Backend, data: Path, work: Path, progress: Progress,
                  keep_safety: bool) -> None:
    """With the backend stopped: optionally save what is there, then put the
    new data in, and the saved ones back if that fails."""
    safety = BACKUP_DIR / archive_format.backup_name(backend.key, datetime.now(), True)
    if keep_safety:
        progress.step("saving_current")
        write_backup(backend, safety)
    progress.step("restoring")
    if docker_compose.restore_volume(backend.key, backend.data_dir, backend.archive_skip, data).ok:
        return
    if keep_safety:
        _put_back(backend, safety, work)
    raise JobFailed("restore_failed", backend.key)


def restore(backend: Backend, bundle: Path, progress: Progress, keep_safety: bool = True) -> None:
    """Replaces the backend's data with the bundle's. keep_safety=False is
    for the demo reset, whose data are disposable by definition."""
    _check_space(BACKUP_DIR)
    with tempfile.TemporaryDirectory(dir=BACKUP_DIR) as tmp:
        work = Path(tmp)
        progress.step("checking")
        data, meta = check_bundle(backend, bundle, work)
        if meta.get("image") and meta["image"] != docker_compose.image_of(backend.key):
            progress.warn("archive_other_version")
        with backend_stopped(backend, progress):
            _replace_data(backend, data, work, progress, keep_safety)
    if keep_safety:
        _prune(backend.key)


def list_backups() -> list[dict]:
    rows = []
    for path in sorted(BACKUP_DIR.glob("*.tar"), key=lambda p: p.name, reverse=True):
        parts = archive_format.parse_backup_name(path.name)
        if parts is None:
            continue
        rows.append({"name": path.name, "size": path.stat().st_size, **parts})
    return rows


def path_of(name: str) -> Path | None:
    """The file behind a name from a request, only if it is one of ours."""
    if archive_format.parse_backup_name(name) is None:
        return None
    path = BACKUP_DIR / name
    return path if path.is_file() else None
