"""The few things the service does as root: restart, shut down, set the clock.

They go through one root-owned helper (system/host-helper.sh, installed to
HELPER below) that knows a fixed list of verbs. sudoers lets the service
user run that helper and nothing else. Arguments are checked here and again
in the helper; neither side builds a shell string.
"""

import logging
import subprocess

log = logging.getLogger(__name__)

HELPER = "/usr/local/libexec/spoolmanscale-pro/host-helper"
HELPER_TIMEOUT_S = 30

# 2024-01-01 and 2100-01-01 in epoch seconds. A clock from a browser outside
# this range is a broken browser, not a time worth setting.
EPOCH_MIN_S = 1704067200
EPOCH_MAX_S = 4102444800


def _helper(*args: str) -> bool:
    try:
        done = subprocess.run(["sudo", "--non-interactive", HELPER, *args],
                              capture_output=True, text=True, timeout=HELPER_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.error("host-helper %s could not run: %s", args[0], e)
        return False
    if done.returncode != 0:
        log.error("host-helper %s failed (%d): %s", args[0], done.returncode,
                  (done.stdout + done.stderr).strip()[-300:])
        return False
    return True


def valid_epoch(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) \
        and EPOCH_MIN_S <= value <= EPOCH_MAX_S


def set_clock(epoch_s: int) -> bool:
    if not valid_epoch(epoch_s):
        return False
    return _helper("set-time", str(epoch_s))


def reboot() -> bool:
    return _helper("reboot")


def poweroff() -> bool:
    return _helper("poweroff")
