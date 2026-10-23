"""Newer versions of a backend: finding them, with their release notes, and
installing one as a job.

The version a backend runs is the one the owner chose (settings
"backend_versions") or else the default compose/docker-compose.yml was
tested with. Installing:
  1. check the version still exists on ghcr.io,
  2. back up the backend's data ("before-update"),
  3. pull the image (the backend keeps running meanwhile),
  4. if it was running: recreate it with the new image and wait until it
     answers; if it does not, put the old version and the backup back.
A database migrated by a newer version cannot always be read by the older
one, which is why step 4 restores the backup and not only the version.
"""

import logging
import re

from . import backups, docker_compose, health, release_sources, settings
from . import version_rules as vr
from .backends import Backend
from .jobs import JobFailed, Progress
from .paths import BACKUP_DIR, COMPOSE_FILE
from .release_sources import SourceError

log = logging.getLogger(__name__)


def compose_default_version(compose_text: str, backend: Backend) -> str | None:
    """The tag after ":-" in ${<VERSION_ENV>:-<tag>} of the compose file."""
    match = re.search(r"\$\{" + re.escape(backend.version_env) + r":-([^}]+)\}", compose_text)
    return match.group(1) if match else None


def default_version(backend: Backend) -> str:
    return compose_default_version(COMPOSE_FILE.read_text(encoding="utf-8"), backend) or ""


def current_version(backend: Backend) -> str:
    chosen = settings.load()["backend_versions"].get(backend.key)
    return chosen if isinstance(chosen, str) and chosen else default_version(backend)


def _notes(backend: Backend, current: str, target: str) -> list[dict]:
    """Release notes between the two, or none if GitHub does not answer:
    the notes are a courtesy, the update does not depend on them."""
    try:
        return vr.releases_between(release_sources.releases(backend.github), current, target)
    except SourceError as e:
        log.info("No release notes for %s: %s", backend.key, e)
        return []


def check(backend: Backend) -> dict:
    """What can be installed. Raises SourceError when ghcr.io is out of reach."""
    current = current_version(backend)
    include_pre = settings.load()["include_prereleases"]
    newer = vr.newer_than(release_sources.image_tags(backend.image), current, include_pre)
    return {
        "key": backend.key, "current": current, "default": default_version(backend),
        "newer": newer,
        "notes": _notes(backend, current, newer[0]) if newer else [],
    }


def _set_version(backend: Backend, tag: str | None) -> None:
    """tag None goes back to the tested default."""
    versions = dict(settings.load()["backend_versions"])
    if tag is None or tag == default_version(backend):
        versions.pop(backend.key, None)
    else:
        versions[backend.key] = tag
    settings.update({"backend_versions": versions})


def _roll_back(backend: Backend, previous: str, backup_name: str | None, progress: Progress) -> None:
    progress.step("rolling_back")
    _set_version(backend, previous)
    if backup_name:
        backups.restore(backend, BACKUP_DIR / backup_name, progress, keep_safety=False)
    elif docker_compose.up(backend.key).ok:
        health.wait_until_ready(backend)


def install(backend: Backend, tag: str, progress: Progress) -> None:
    progress.step("checking_version")
    try:
        available = release_sources.image_tags(backend.image)
    except SourceError as e:
        raise JobFailed(e.code, str(e)) from e
    if tag not in available or vr.parse(tag) is None:
        raise JobFailed("unknown_version", tag)
    states = docker_compose.states() or {}
    was_running = states.get(backend.key) == "running"
    previous = current_version(backend)
    old_image = docker_compose.image_of(backend.key)
    backup_name = None
    if states.get(backend.key, "absent") != "absent":
        backup_name = backups.create(backend, progress, reason="before-update")
    _set_version(backend, tag)
    progress.step("pulling")
    if not docker_compose.pull(backend.key).ok:
        _set_version(backend, previous)
        raise JobFailed("pull_failed", tag)
    progress.set_result(version=tag, backup=backup_name)
    if not was_running:
        return
    progress.step("starting")
    if docker_compose.up(backend.key).ok and health.wait_until_ready(backend):
        # The old image is no longer used by anything; a backend image is
        # up to 1.8 GB, and a few updates would fill the SD card.
        docker_compose.remove_image(old_image)
        return
    new_image = docker_compose.image_of(backend.key)
    _roll_back(backend, previous, backup_name, progress)
    docker_compose.remove_image(new_image)
    raise JobFailed("update_rolled_back", f"{backend.key} {tag} -> {previous}")
