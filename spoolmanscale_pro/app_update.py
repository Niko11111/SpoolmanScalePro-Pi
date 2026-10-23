"""Updating SpoolmanScale Pro itself from its GitHub releases.

The release workflow (.github/workflows/release.yml) publishes an archive
and its checksum for every tag. Here: which newer release there is, with
its notes; starting the install (host-helper self-update, which downloads,
checks and runs the release's install.sh as a systemd unit of its own,
because install.sh restarts this service); and going back to the release
installed before (host-helper self-rollback).

Pre-releases are offered to a Pi that runs one itself, or when the owner
switched them on: whoever installed a beta follows the betas.
"""

import logging
import re
import subprocess
from pathlib import Path

from . import os_update_rules, release_sources, settings
from . import version_rules as vr
from .host_actions import run_helper
from .paths import APP_ROOT
from .version import APP_VERSION

log = logging.getLogger(__name__)

REPOSITORY = "Niko11111/SpoolmanScalePro-Pi"
# The names host-helper.sh uses.
SELF_UPDATE_UNIT = "spoolmanscale-pro-self-update"
SELF_UPDATE_LOG = Path("/var/log/spoolmanscale-pro/self-update.log")
# The same form as VERSION (check_conventions.py) and the helper's check.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-beta\.\d+)?$")
LOG_TAIL_LINES = 30
EXIT_ALREADY_RUNNING = 5


def archive_name(version: str) -> str:
    return f"spoolmanscale-pro-{version}.tar.gz"


def offers_prereleases() -> bool:
    current = vr.parse(APP_VERSION)
    return settings.load()["include_prereleases"] or bool(current and current["prerelease"])


def installable(releases: list[dict], current: str, include_pre: bool) -> list[dict]:
    """Releases newer than current that carry their archive, newest first.
    Pure; tested."""
    with_archive = [r for r in releases if archive_name(vr.normalize(r["tag"])) in r.get("assets", [])
                    and (include_pre or not r.get("prerelease"))]
    tags = vr.newer_than([r["tag"] for r in with_archive], current, include_pre)
    return [next(r for r in with_archive if r["tag"] == tag) for tag in tags]


def previous_release() -> str | None:
    """The version installed before this one, still on the Pi, or None (a
    first install, or a checkout on a laptop)."""
    releases_dir = APP_ROOT.parent
    if releases_dir.name != "releases":
        return None
    others = [p for p in releases_dir.iterdir() if p.is_dir() and p.resolve() != APP_ROOT.resolve()]
    if not others:
        return None
    return max(others, key=lambda p: p.stat().st_mtime).name


def check() -> dict:
    """Raises release_sources.SourceError when GitHub is out of reach."""
    found = installable(release_sources.releases(REPOSITORY), APP_VERSION, offers_prereleases())
    return {"newer": [vr.normalize(r["tag"]) for r in found],
            "notes": vr.releases_between(found, APP_VERSION, found[0]["tag"]) if found else []}


def start_update(version: str) -> str:
    """'started', 'running' (one runs already) or 'failed'."""
    result = run_helper("self-update", version)
    if result.ok:
        log.info("Update to %s started", version)
        return "started"
    return "running" if result.code == EXIT_ALREADY_RUNNING else "failed"


def rollback() -> bool:
    return run_helper("self-rollback").ok


def update_state() -> dict:
    """Whether an update runs, and the end of its log."""
    try:
        running = subprocess.run(["systemctl", "is-active", "--quiet", SELF_UPDATE_UNIT],
                                 timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        running = False
    try:
        text = SELF_UPDATE_LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return {"running": running, "exit": os_update_rules.exit_code(text),
            "lines": [line for line in text.splitlines() if line.strip()][-LOG_TAIL_LINES:]}
