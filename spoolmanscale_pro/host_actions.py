"""The things the service does as root: restart, shut down, set the clock,
set the host name, and change the WLAN.

They go through one root-owned helper (system/host-helper.sh, installed to
HELPER below) that knows a fixed list of verbs. sudoers lets the service
user run that helper and nothing else. Arguments are checked here and again
in the helper; neither side builds a shell string. Secrets go to the helper
on stdin, never as arguments, so they show up in no process list and no log.
"""

import logging
import subprocess
from dataclasses import dataclass

log = logging.getLogger(__name__)

HELPER = "/usr/local/libexec/spoolmanscale-pro/host-helper"
HELPER_TIMEOUT_S = 30
# Joining a WLAN waits up to 45 s in the helper, then falls back for 30 s.
NETWORK_TIMEOUT_S = 120

# 2024-01-01 and 2100-01-01 in epoch seconds. A clock from a browser outside
# this range is a broken browser, not a time worth setting.
EPOCH_MIN_S = 1704067200
EPOCH_MAX_S = 4102444800

# Exit codes of host-helper.sh beyond plain failure.
EXIT_WIFI_FAILED = 3
EXIT_NO_OTHER_NETWORK = 4


@dataclass(frozen=True)
class HelperResult:
    code: int
    output: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def run_helper(*args: str, stdin_text: str | None = None,
               timeout_s: int = HELPER_TIMEOUT_S) -> HelperResult:
    try:
        done = subprocess.run(["sudo", "--non-interactive", HELPER, *args],
                              input=stdin_text, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.error("host-helper %s could not run: %s", args[0], e)
        return HelperResult(-1, "")
    if done.returncode != 0:
        # stderr only: stdout of a scan is data, and stdin is never echoed.
        log.error("host-helper %s failed (%d): %s", args[0], done.returncode,
                  done.stderr.strip()[-300:])
    return HelperResult(done.returncode, done.stdout)


def valid_epoch(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) \
        and EPOCH_MIN_S <= value <= EPOCH_MAX_S


def set_clock(epoch_s: int) -> bool:
    if not valid_epoch(epoch_s):
        return False
    return run_helper("set-time", str(epoch_s)).ok


def reboot() -> bool:
    return run_helper("reboot").ok


def poweroff() -> bool:
    return run_helper("poweroff").ok
