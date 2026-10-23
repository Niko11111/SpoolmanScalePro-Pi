"""Updating Raspberry Pi OS, as in TheRentalScale: first a search that
installs nothing and lists every package, then the upgrade with its log live
on the page.

The upgrade runs as a systemd unit of its own (host-helper os-upgrade-start),
so a restart of this service cannot cut dpkg off halfway. follow() reads the
unit's log; it can be started again for an upgrade that is already running,
e.g. after the page or the service was restarted.

Parsing: os_update_rules.py.
"""

import logging
import os
import platform
import subprocess
import time
from pathlib import Path

from . import os_update_rules as rules
from .host_actions import run_helper
from .jobs import JobFailed, Progress

log = logging.getLogger(__name__)

# The names host-helper.sh uses (UPGRADE_UNIT, UPGRADE_LOG).
UPGRADE_UNIT = "spoolmanscale-pro-os-upgrade"
UPGRADE_LOG = Path("/var/log/spoolmanscale-pro/os-upgrade.log")
REBOOT_REQUIRED_FLAG = Path("/run/reboot-required")
MODULES_DIR = Path("/lib/modules")

# apt-get update fetches from the Debian and Raspberry Pi mirrors; slow over
# 2.4 GHz WLAN, but it ends.
CHECK_TIMEOUT_S = 600
# A full upgrade on a Pi 3 with a new kernel takes a long while.
UPGRADE_LIMIT_S = 90 * 60
POLL_S = 2
EXIT_ALREADY_RUNNING = 5
# Enough of the log's end to find the exit line; the page gets every line
# as it comes, the full log stays on the Pi.
TAIL_BYTES = 4096


def check(progress: Progress) -> None:
    progress.step("refreshing_packages")
    result = run_helper("apt-check", timeout_s=CHECK_TIMEOUT_S)
    if not result.ok:
        raise JobFailed("os_check_failed")
    progress.set_result(**rules.build_result(result.output))


def upgrade_running() -> bool:
    try:
        done = subprocess.run(["systemctl", "is-active", "--quiet", UPGRADE_UNIT], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False  # no systemd (a laptop): nothing can be running
    return done.returncode == 0


def restart_needed() -> bool:
    if REBOOT_REQUIRED_FLAG.exists():
        return True
    try:
        installed = os.listdir(MODULES_DIR)
    except OSError:
        return False
    return rules.kernel_restart_needed(platform.release(), installed)


def _read_from(offset: int) -> tuple[str, int]:
    try:
        with open(UPGRADE_LOG, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return "", offset
    return data.decode("utf-8", "replace"), offset + len(data)


def follow(progress: Progress) -> None:
    """Shows the running upgrade's log until the unit has ended, then
    reports how it ended."""
    progress.step("upgrading")
    offset, text, deadline = 0, "", time.monotonic() + UPGRADE_LIMIT_S
    while True:
        chunk, offset = _read_from(offset)
        if chunk:
            text = (text + chunk)[-TAIL_BYTES:]
            progress.output([line for line in chunk.splitlines() if line.strip()])
        if not upgrade_running() or time.monotonic() > deadline:
            break
        time.sleep(POLL_S)
    chunk, offset = _read_from(offset)
    if chunk:
        progress.output([line for line in chunk.splitlines() if line.strip()])
    code = rules.exit_code((text + chunk)[-TAIL_BYTES:])
    if code is None:
        raise JobFailed("os_upgrade_interrupted")
    if code != 0:
        raise JobFailed("os_upgrade_failed", f"apt exit {code}")
    progress.set_result(restart_needed=restart_needed())


def upgrade(progress: Progress) -> None:
    started = run_helper("os-upgrade-start")
    if not started.ok and started.code != EXIT_ALREADY_RUNNING:
        raise JobFailed("os_upgrade_failed", "could not start")
    follow(progress)
