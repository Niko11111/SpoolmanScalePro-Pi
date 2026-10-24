"""Remote access through Tailscale, from a button on the System page:
install it, connect (the owner opens the login link Tailscale gives),
disconnect.

Installing and connecting run in a systemd unit of the root helper with a
log, which the page shows while they run (host-helper.sh, tailscale_*).
parse_status() reads `tailscale status --json` and is pure and tested.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path

from . import os_update_rules
from .host_actions import run_helper

log = logging.getLogger(__name__)

# The names host-helper.sh uses.
UNIT = "spoolmanscale-pro-tailscale"
LOG = Path("/var/log/spoolmanscale-pro/tailscale.log")
LOG_TAIL_LINES = 40
EXIT_BUSY = 5


def parse_status(text: str) -> dict:
    """The parts of `tailscale status --json` the page shows."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"state": "unknown"}
    me = data.get("Self") or {}
    return {
        # NeedsLogin, Running, Stopped, Starting, NoState
        "state": data.get("BackendState", "unknown"),
        "auth_url": data.get("AuthURL", ""),
        "addresses": me.get("TailscaleIPs") or [],
        "name": (me.get("DNSName") or "").rstrip("."),
        "tailnet": (data.get("CurrentTailnet") or {}).get("Name", ""),
    }


def _unit_running() -> bool:
    try:
        return subprocess.run(["systemctl", "is-active", "--quiet", UNIT], timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _log_tail() -> tuple[list[str], int | None]:
    try:
        text = LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], None
    return os_update_rules.log_lines(text)[-LOG_TAIL_LINES:], os_update_rules.exit_code(text)


def status() -> dict:
    lines, exit_code = _log_tail()
    view = {"installed": shutil.which("tailscale") is not None, "busy": _unit_running(),
            "lines": lines, "exit": exit_code}
    if view["installed"]:
        result = run_helper("tailscale-status")
        view.update(parse_status(result.output) if result.ok else {"state": "unknown"})
    return view


def _start(verb: str) -> str:
    """'started', 'busy' or 'failed'."""
    result = run_helper(verb)
    if result.ok:
        return "started"
    return "busy" if result.code == EXIT_BUSY else "failed"


def install() -> str:
    return _start("tailscale-install")


def connect() -> str:
    return _start("tailscale-up")


def disconnect() -> bool:
    return run_helper("tailscale-down").ok
