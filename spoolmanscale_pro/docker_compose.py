"""Drives the backends through `docker compose`.

Every command is an argument list, never a shell string, so nothing a
request carries can turn into a command. The backend key is checked against
the registry before it reaches this module. The one shell script here
(_RESTORE_SCRIPT) is a constant that runs inside a throwaway container and
takes its values as positional arguments, never pasted into its text.

parse_ps_output() is pure and tested; the rest is a thin wrapper whose
failures come back as a CommandResult rather than an exception, because
every caller has to show them to someone.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import backend_secrets, settings
from .backends import BACKEND_KEYS, BACKENDS
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
    """The service's environment, the host time zone for ${TZ}, the
    backends' logins (backend_secrets.py) and the versions chosen on the
    Updates page (SPOOLMAN_VERSION ...)."""
    env = dict(os.environ)
    env.update(backend_secrets.compose_environment())
    chosen = settings.load()["backend_versions"]
    for backend in BACKENDS:
        tag = chosen.get(backend.key)
        if isinstance(tag, str) and tag:
            env[backend.version_env] = tag
    try:
        tz = HOST_TIMEZONE_FILE.read_text(encoding="utf-8").strip()
        if tz:
            env["TZ"] = tz
    except OSError:
        pass  # no /etc/timezone (a laptop): the compose default applies
    return env


def _base_command() -> list[str]:
    cmd = ["docker", "compose", "--project-name", PROJECT_NAME,
           "--file", str(COMPOSE_FILE)]
    # Every profile, so `ps` and `stop` see services that are not the one
    # being started.
    for key in BACKEND_KEYS:
        cmd += ["--profile", key]
    return cmd


def _run(args: list[str], timeout_s: int) -> CommandResult:
    cmd = _base_command() + args
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


# A backup or restore runs tar in a throwaway container of the backend's own
# image, as root inside it, so the service needs no rights on the volume's
# files and ownership comes back exactly as it was (--numeric-owner).
ARCHIVE_TIMEOUT_S = 600

# Runs inside the throwaway container. $1 is the data directory, the
# remaining arguments the top-level names to keep. Empties the directory
# except those, then unpacks the archive from stdin.
_RESTORE_SCRIPT = """set -e
cd "$1"; shift
for entry in ./* ./.[!.]*; do
  [ -e "$entry" ] || continue
  keep=0
  for name in "$@"; do [ "${entry#./}" = "$name" ] && keep=1; done
  [ "$keep" = 1 ] || rm -rf -- "$entry"
done
tar --numeric-owner -xzf -
"""


def _run_with_file(args: list[str], stdin=None, stdout=None) -> CommandResult:
    """Like _run, but one end of the command is a file: the archive."""
    cmd = _base_command() + args
    try:
        done = subprocess.run(cmd, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
                              timeout=ARCHIVE_TIMEOUT_S, env=_environment())
    except subprocess.TimeoutExpired:
        log.error("docker compose run timed out after %d s", ARCHIVE_TIMEOUT_S)
        return CommandResult(False, f"timed out after {ARCHIVE_TIMEOUT_S} s")
    except OSError as e:
        log.error("docker compose run could not start: %s", e)
        return CommandResult(False, str(e))
    errors = done.stderr.decode("utf-8", "replace").strip()
    if done.returncode != 0:
        log.error("docker compose run failed (%d): %s", done.returncode, errors[-500:])
    return CommandResult(done.returncode == 0, errors)


def _throwaway(key: str, entrypoint: str) -> list[str]:
    return ["run", "--rm", "--no-deps", "-T", "--user", "0", "--entrypoint", entrypoint, key]


def archive_volume(key: str, data_dir: str, skip: tuple[str, ...], dest: Path) -> CommandResult:
    """Packs data_dir of the backend's volume into dest (tar.gz). The
    backend must be stopped, or a database is caught mid-write."""
    excludes = [f"--exclude=./{name}" for name in skip]
    with open(dest, "wb") as out:
        return _run_with_file(_throwaway(key, "tar") +
                              ["--numeric-owner", *excludes, "-C", data_dir, "-czf", "-", "."],
                              stdout=out)


def restore_volume(key: str, data_dir: str, skip: tuple[str, ...], source: Path) -> CommandResult:
    """Replaces data_dir of the backend's volume with source (tar.gz),
    leaving the top-level names in skip alone. The backend must be stopped."""
    with open(source, "rb") as src:
        return _run_with_file(_throwaway(key, "sh") +
                              ["-c", _RESTORE_SCRIPT, "sh", data_dir, *skip], stdin=src)


def image_of(key: str) -> str:
    """The image the compose file names for a backend, e.g.
    ghcr.io/fire-devils/filaman-system:v1.4.3. Empty when unknown."""
    result = _run(["config", "--format", "json"], QUERY_TIMEOUT_S)
    if not result.ok:
        return ""
    try:
        return json.loads(result.output)["services"][key]["image"]
    except (json.JSONDecodeError, KeyError, TypeError):
        log.error("docker compose config gave no image for %s", key)
        return ""


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
