"""Drives the backends through `docker compose`.

Every command is an argument list, never a shell string, so nothing a
request carries can turn into a command. The backend key is checked against
the registry before it reaches this module.

parse_ps_output() is pure and tested; the rest is a thin wrapper whose
failures come back as a CommandResult rather than an exception, because
every caller has to show them to someone.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass

from .backends import BACKEND_KEYS
from .paths import COMPOSE_FILE, HOST_TIMEZONE_FILE

log = logging.getLogger(__name__)

PROJECT_NAME = "spoolmanscale-pro"

# Starting is quick once the image is there. The first start of a backend
# pulls it, which over 2.4 GHz WLAN on a Pi takes minutes.
UP_TIMEOUT_S = 900
STOP_TIMEOUT_S = 90
QUERY_TIMEOUT_S = 20
LOG_TAIL_LINES = 80


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    output: str


def _environment() -> dict:
    """The service's environment plus the host time zone for ${TZ}."""
    env = dict(os.environ)
    try:
        tz = HOST_TIMEZONE_FILE.read_text(encoding="utf-8").strip()
        if tz:
            env["TZ"] = tz
    except OSError:
        pass  # no /etc/timezone (a laptop): the compose default applies
    return env


def _run(args: list[str], timeout_s: int) -> CommandResult:
    cmd = ["docker", "compose", "--project-name", PROJECT_NAME,
           "--file", str(COMPOSE_FILE)]
    # Every profile, so `ps` and `stop` see services that are not the one
    # being started.
    for key in BACKEND_KEYS:
        cmd += ["--profile", key]
    cmd += args
    try:
        done = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout_s, env=_environment())
    except subprocess.TimeoutExpired:
        log.error("docker compose %s timed out after %d s", args[0], timeout_s)
        return CommandResult(False, f"timed out after {timeout_s} s")
    except OSError as e:
        log.error("docker compose %s could not start: %s", args[0], e)
        return CommandResult(False, str(e))
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0:
        log.error("docker compose %s failed (%d): %s", args[0], done.returncode, output[-500:])
    return CommandResult(done.returncode == 0, output)


def up(key: str) -> CommandResult:
    return _run(["up", "--detach", key], UP_TIMEOUT_S)


def stop(key: str) -> CommandResult:
    return _run(["stop", key], STOP_TIMEOUT_S)


def pull(key: str) -> CommandResult:
    return _run(["pull", key], UP_TIMEOUT_S)


def logs(key: str) -> CommandResult:
    return _run(["logs", "--no-color", "--tail", str(LOG_TAIL_LINES), key], QUERY_TIMEOUT_S)


def parse_ps_output(text: str) -> dict[str, str]:
    """Maps service name to container state ("running", "exited", ...).

    Compose prints one JSON object per line since 2.21 and a single JSON
    array before that; both are accepted.
    """
    text = text.strip()
    if not text:
        return {}
    if text.startswith("["):
        rows = json.loads(text)
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return {r.get("Service", ""): r.get("State", "") for r in rows if r.get("Service")}


def states() -> dict[str, str] | None:
    """Every backend container that exists and its state, or None when
    Docker itself did not answer."""
    result = _run(["ps", "--all", "--format", "json"], QUERY_TIMEOUT_S)
    if not result.ok:
        return None
    try:
        return parse_ps_output(result.output)
    except (json.JSONDecodeError, AttributeError) as e:
        log.error("docker compose ps gave output that is not JSON: %s", e)
        return None
