"""A backend's daily build (Backend.daily_tag; today BamBuddy's "daily"):
switching to it, following it, and leaving it again.

The daily tag moves every day, so the Pi pins the image it installed:
settings "backend_versions" holds daily@sha256:..., and the backend stays
on exactly that build until the owner installs a newer one. Which GitHub
pre-release that build was (v1.3.0b1-daily.20261024) is kept in
"daily_releases"; it names the build on the page and is the floor a
release must clear to count as newer.

A daily build may migrate the database beyond what the last release can
read. So there are two ways back:
  - a release newer than the daily build (1.3.0 after 1.3.0b1): a normal
    update, nothing is lost (backend_updates.install);
  - at once, to the release from before: only with the "before-daily"
    backup made when switching, which replaces everything changed since.
    The data of the daily build are kept as a "before-restore" backup.
Nothing here installs on its own; each step is a job the owner starts.
"""

import logging

from . import archive_format, backend_updates, backups, docker_compose, release_sources, settings
from . import version_rules as vr
from .archive_format import ArchiveError
from .backends import Backend
from .jobs import JobFailed, Progress
from .paths import BACKUP_DIR
from .release_sources import SourceError

log = logging.getLogger(__name__)

SWITCH_REASON = "before-daily"


def _newest_release(backend: Backend) -> dict | None:
    """The newest daily build's GitHub pre-release, None when GitHub does
    not answer: it only names the build."""
    try:
        return vr.newest_daily(release_sources.releases(backend.github))
    except SourceError as e:
        log.info("No daily release notes for %s: %s", backend.key, e)
        return None


def _way_back(backend: Backend) -> dict | None:
    """The backup from before the switch and the release it was made with."""
    path = backups.newest(backend.key, SWITCH_REASON)
    if path is None:
        return None
    try:
        image = archive_format.read_meta(path).get("image", "")
    except ArchiveError as e:
        log.warning("Backup %s before the daily build is unreadable: %s", path.name, e)
        return None
    tag = vr.image_tag(image)
    return {"backup": path.name,
            "version": tag if vr.parse(tag) else backend_updates.default_version(backend)}


def check(backend: Backend) -> dict:
    """backend_updates.check() plus the daily build: whether the backend
    runs one, which, whether a newer one is out, and the way back. Raises
    SourceError when ghcr.io is out of reach."""
    current = backend_updates.current_version(backend)
    on = vr.is_daily(current, backend.daily_tag)
    newest = _newest_release(backend)
    installed = settings.load()["daily_releases"].get(backend.key) if on else None
    floor = (installed or newest or {}).get("tag") if on else None
    found = backend_updates.check(backend, floor)
    found["daily"] = {
        "on": on, "installed": installed, "newest": newest,
        "update": on and vr.pinned_digest(current) != release_sources.tag_digest(backend.image, backend.daily_tag),
        "back": _way_back(backend) if on else None,
    }
    return found


def install(backend: Backend, progress: Progress) -> None:
    """Switches to the daily build, or to a newer one when it runs one."""
    progress.step("checking_version")
    if not backend.daily_tag:
        raise JobFailed("no_daily_build", backend.key)
    try:
        digest = release_sources.tag_digest(backend.image, backend.daily_tag)
    except SourceError as e:
        raise JobFailed(e.code, str(e)) from e
    current = backend_updates.current_version(backend)
    target = vr.pin(backend.daily_tag, digest)
    if target == current:
        raise JobFailed("already_installed", target)
    first = not vr.is_daily(current, backend.daily_tag)
    backend_updates.apply_version(backend, target, progress, SWITCH_REASON if first else "before-update")
    release = _newest_release(backend)
    releases = dict(settings.load()["daily_releases"])
    releases[backend.key] = {"tag": release["tag"], "published": release["published"]} if release else None
    settings.update({"daily_releases": releases})


def leave(backend: Backend, progress: Progress) -> None:
    """Back to the release from before the daily build, with its backup."""
    current = backend_updates.current_version(backend)
    if not vr.is_daily(current, backend.daily_tag):
        raise JobFailed("not_on_daily_build", backend.key)
    way = _way_back(backend)
    if way is None:
        raise JobFailed("no_backup_before_daily", backend.key)
    was_running = (docker_compose.states() or {}).get(backend.key) == "running"
    daily_image = docker_compose.image_of(backend.key)
    backend_updates.set_version(backend, way["version"])
    progress.set_result(version=way["version"], backup=way["backup"])
    progress.step("pulling")
    if not docker_compose.pull(backend.key).ok:
        backend_updates.set_version(backend, current)
        raise JobFailed("pull_failed", way["version"])
    try:
        # Stops the backend if it runs, puts the data back and starts it
        # again, now with the release.
        backups.restore(backend, BACKUP_DIR / way["backup"], progress)
    except JobFailed:
        # The daily data are back in place (backups.restore); the daily
        # build has to come back with them.
        backend_updates.set_version(backend, current)
        if was_running:
            docker_compose.up(backend.key)
        raise
    docker_compose.remove_image(daily_image)
