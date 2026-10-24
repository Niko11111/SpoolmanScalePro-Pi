"""Credentials this Pi hands to a backend when it starts it.

FilaMan creates its first admin only from ADMIN_EMAIL and ADMIN_PASSWORD
(backend/app/core/seeds/__init__.py, seed_admin_user_from_env); it has no
page to register one. Without them a FilaMan started here would have no
user at all. So the first time it is needed, a login with a random password
is made here, kept in SECRETS_FILE (0600) and passed in through
docker_compose's environment on every start.

It must never change afterwards: FilaMan only creates the admin when no
user with that e-mail exists, so a new e-mail would add a second admin and
a new password would do nothing. The owner sees it on the page, logs in to
FilaMan with it, and may change the password there.
"""

import json
import logging
import os
import secrets
import threading

from .paths import SECRETS_FILE

log = logging.getLogger(__name__)

FILAMAN_ADMIN_EMAIL = "admin@spoolmanscale.local"
PASSWORD_BYTES = 12

_lock = threading.Lock()


def _load() -> dict:
    try:
        data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        # Not regenerated: a new password would not reach a FilaMan that
        # already has its admin, and the old one would be lost for good.
        log.error("Backend credentials unreadable: %s", e)
        raise
    return data if isinstance(data, dict) else {}


def _store(data: dict) -> None:
    tmp = SECRETS_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SECRETS_FILE)


def filaman_admin() -> dict:
    """{"email": ..., "password": ...}, made on first use."""
    with _lock:
        data = _load()
        entry = data.get("filaman")
        if not isinstance(entry, dict) or not entry.get("password"):
            entry = {"email": FILAMAN_ADMIN_EMAIL, "password": secrets.token_urlsafe(PASSWORD_BYTES)}
            data["filaman"] = entry
            _store(data)
            log.info("FilaMan admin login created for %s", entry["email"])
        return dict(entry)


def compose_environment() -> dict:
    """What docker compose needs from here, as environment variables."""
    admin = filaman_admin()
    return {"FILAMAN_ADMIN_EMAIL": admin["email"], "FILAMAN_ADMIN_PASSWORD": admin["password"]}
