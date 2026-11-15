"""Newer versions of a backend: finding them, with their release notes, and
installing one as a job.

The version a backend runs is the one the owner chose (settings
"backend_versions"). A backend started for the first time takes the newest
release on ghcr.io (Nikolai, 15.11.2026: no versions written into this
service); the default in compose/docker-compose.yml is only the fallback
when ghcr.io is out of reach. Installing a newer one:
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
import threading
import time

from . import backups, docker_compose, health, release_sources, settings
from . import version_rules as vr
from .backends import BACKENDS, Backend
from .jobs import JobFailed, Progress
from .paths import BACKUP_DIR, COMPOSE_FILE
from .release_sources import SourceError

log = logging.getLogger(__name__)

# Docker can come up after this service at boot.
KEEP_VERSIONS_TRIES = 20
KEEP_VERSIONS_WAIT_S = 30


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


def check(backend: Backend, floor: str | None = None) -> dict:
    """What can be installed. floor: the version newer ones are counted
    from, when the one running is not a version itself (a daily build).
    Raises SourceError when ghcr.io is out of reach."""
    current = current_version(backend)
    floor = floor or current
    include_pre = settings.load()["include_prereleases"]
    newer = vr.newer_than(release_sources.image_tags(backend.image), floor, include_pre)
    return {
        "key": backend.key, "current": current, "shown": vr.display(current), "default": default_version(backend),
        "newer": newer,
        "notes": _notes(backend, floor, newer[0]) if newer else [],
    }


def set_version(backend: Backend, tag: str | None) -> None:
    """tag None goes back to the default in the compose file."""
    versions = dict(settings.load()["backend_versions"])
    if tag is None or tag == default_version(backend):
        versions.pop(backend.key, None)
    else:
        versions[backend.key] = tag
    settings.update({"backend_versions": versions})


def is_first_start(chosen: str | None, has_container: bool, has_data: bool) -> bool:
    """Only a backend that never ran picks its version: one with a container
    or a data volume keeps what it has, or a newer version would migrate its
    database without a backup."""
    return not chosen and not has_container and not has_data


def newest_release(backend: Backend) -> str | None:
    """The newest stable version on ghcr.io, None when it is out of reach."""
    try:
        found = vr.versions(release_sources.image_tags(backend.image), False)
    except SourceError as e:
        log.info("Newest %s not found, the compose default applies: %s", backend.key, e)
        return None
    return found[0] if found else None


def choose_first_version(backend: Backend) -> str | None:
    """Before a start: a backend that never ran gets the newest release.
    Returns the version chosen, None when it keeps what it has. Anything
    unclear (Docker or ghcr.io not answering) leaves the default."""
    containers, volumes = docker_compose.container_images(), docker_compose.data_volumes()
    if containers is None or volumes is None:
        return None
    chosen = settings.load()["backend_versions"].get(backend.key)
    if not is_first_start(chosen, backend.key in containers, f"{backend.key}-data" in volumes):
        return None
    newest = newest_release(backend)
    if newest:
        log.info("%s starts for the first time, with the newest release %s", backend.key, newest)
        set_version(backend, newest)
    return newest


def undo_first_version(backend: Backend, chosen: str | None) -> None:
    """After a start that failed before a container existed (the download
    broke off, no image for this Pi): the choice goes, so the next start
    picks again and an image already here can still start offline. Once a
    container ran the version, it stays: it may have written the data."""
    if not chosen:
        return
    containers = docker_compose.container_images()
    if containers is not None and backend.key not in containers:
        log.info("%s did not start on %s, back to choosing at the next start", backend.key, chosen)
        set_version(backend, None)


def versions_to_keep(chosen: dict, installed: dict, defaults: dict) -> dict:
    """Which backends have to be held at the version they have. A new release
    of this service can move a default in the compose file. Without a choice
    on record the next start would then pull that version and migrate the
    backend's database: no backup, and no way back."""
    return {key: tag for key, tag in installed.items()
            if key not in chosen and tag != defaults.get(key) and vr.parse(tag) is not None}


def keep_installed_versions() -> bool:
    """False while Docker does not answer."""
    images = docker_compose.container_images()
    if images is None:
        return False
    chosen = settings.load()["backend_versions"]
    installed = {key: vr.image_tag(image) for key, image in images.items()}
    keep = versions_to_keep(chosen, installed, {b.key: default_version(b) for b in BACKENDS})
    if keep:
        log.info("Keeping the installed versions: %s", keep)
        settings.update({"backend_versions": {**chosen, **keep}})
    return True


def _keep_versions_when_docker_answers() -> None:
    for _ in range(KEEP_VERSIONS_TRIES):
        if keep_installed_versions():
            return
        time.sleep(KEEP_VERSIONS_WAIT_S)
    log.warning("Docker did not answer, installed versions not checked")


def start_keeping_versions() -> None:
    threading.Thread(target=_keep_versions_when_docker_answers, daemon=True, name="keep-versions").start()


def _roll_back(backend: Backend, previous: str, backup_name: str | None, progress: Progress) -> None:
    progress.step("rolling_back")
    set_version(backend, previous)
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
    apply_version(backend, tag, progress)


def apply_version(backend: Backend, tag: str, progress: Progress, reason: str = "before-update") -> None:
    """Steps 2 to 4 above for a tag already checked. reason: the backup's."""
    states = docker_compose.states() or {}
    was_running = states.get(backend.key) == "running"
    previous = current_version(backend)
    old_image = docker_compose.image_of(backend.key)
    backup_name = None
    if states.get(backend.key, "absent") != "absent":
        backup_name = backups.create(backend, progress, reason=reason)
    set_version(backend, tag)
    progress.step("pulling")
    if not docker_compose.pull(backend.key).ok:
        set_version(backend, previous)
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
