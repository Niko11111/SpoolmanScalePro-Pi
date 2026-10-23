"""The service's settings, one JSON file under DATA_DIR.

Reading never fails: a missing or broken file gives the defaults, and the
broken one is logged. Writing goes through a temporary file and a rename,
so a power cut mid-write leaves either the old file or the new one.

clean_update() is the one place a value from outside is checked before it
is stored. It is pure and tested.
"""

import json
import logging
import os
import re
import threading

from .backends import BACKEND_KEYS
from .paths import SETTINGS_FILE

log = logging.getLogger(__name__)

DEFAULTS = {
    "active_backend": None,
    # How the service reaches the scale's web interface: a name such as
    # spoolmanscale.local or an address. Empty means no scale is paired.
    "scale_address": "",
    # The scale's web password, if one is set there. Digits only, the way
    # the scale takes it.
    "scale_password": "",
}

SCALE_ADDRESS_MAX_LEN = 64
# WEB_PASS_MIN and WEB_PASS_MAX in the firmware's web/web_access.h.
SCALE_PASSWORD_MIN_LEN = 4
SCALE_PASSWORD_MAX_LEN = 8
_ADDRESS_RE = re.compile(r"^[A-Za-z0-9.-]+(:[0-9]{1,5})?$")

_lock = threading.Lock()


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return data
    except (OSError, json.JSONDecodeError) as e:
        log.error("Settings file unreadable, using defaults: %s", e)
        return data
    if isinstance(stored, dict):
        data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return data


def _write(data: dict) -> None:
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SETTINGS_FILE)


def update(changes: dict) -> dict:
    """Stores already cleaned values and returns the full new settings."""
    with _lock:
        data = load()
        data.update(changes)
        _write(data)
        return data


def clean_update(raw: dict) -> tuple[dict, list[str]]:
    """Checks the fields a request may change. Returns the cleaned values and
    the names of the fields that were refused."""
    clean, refused = {}, []
    if "scale_address" in raw:
        value = str(raw["scale_address"]).strip().removeprefix("http://").rstrip("/")
        if value == "" or (len(value) <= SCALE_ADDRESS_MAX_LEN and _ADDRESS_RE.match(value)):
            clean["scale_address"] = value
        else:
            refused.append("scale_address")
    if "scale_password" in raw:
        value = str(raw["scale_password"]).strip()
        if value == "" or (value.isdigit() and
                           SCALE_PASSWORD_MIN_LEN <= len(value) <= SCALE_PASSWORD_MAX_LEN):
            clean["scale_password"] = value
        else:
            refused.append("scale_password")
    return clean, refused


def public_view(data: dict) -> dict:
    """The settings as the page may see them: the scale password only as
    whether there is one."""
    view = {k: v for k, v in data.items() if k != "scale_password"}
    view["scale_password_set"] = bool(data.get("scale_password"))
    return view


def valid_backend_key(key) -> bool:
    return isinstance(key, str) and key in BACKEND_KEYS
