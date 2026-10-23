"""Who may use the page: one account (a user name and a password), or none.

The account lives in AUTH_FILE. It is in one of three modes:
  unset     first visit: the page asks for a user name and a password, or
            for the decision to run without one
  password  every /api route except web/access.py's OPEN_ENDPOINTS needs a
            logged-in session (a signed cookie, HttpOnly, SameSite=Lax)
  open      no login at all, chosen by the owner after a warning: the
            service can drive Docker, which amounts to root on the Pi

The user name is there for password managers, which want one to store the
password under. It is checked like the password, so a wrong name and a
wrong password look the same from outside.

Against requests from other sites (CSRF), in every mode: a request that
changes something must carry the X-SSPro header, which a foreign page cannot
set without a CORS preflight this service never answers, and an Origin
header, if present, must name this host.

The hashing and checking functions are pure and tested.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import urllib.parse

from .paths import AUTH_FILE, SESSION_KEY_FILE

log = logging.getLogger(__name__)

MODE_UNSET = "unset"
MODE_PASSWORD = "password"
MODE_OPEN = "open"

PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128
USERNAME_MAX_LEN = 64
DEFAULT_USERNAME = "admin"
# scrypt cost: about 16 MiB and a tenth of a second on a Pi 3.
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16
SESSION_KEY_BYTES = 32

# After this many failed logins in a row, each further try waits.
FAILURES_BEFORE_DELAY = 5
FAILURE_DELAY_S = 30

CSRF_HEADER = "X-SSPro"

_lock = threading.Lock()
_failures = {"count": 0, "last": 0.0}


def hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N,
                            r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN)
    return digest.hex()


def verify(username: str, password: str, record: dict) -> bool:
    """True when both match the record. The hash is computed even for a
    wrong name, so the answer takes as long either way."""
    try:
        salt = bytes.fromhex(record["salt"])
        expected = record["hash"]
    except (KeyError, ValueError, TypeError):
        return False
    password_ok = hmac.compare_digest(hash_password(password, salt), expected)
    stored_name = str(record.get("user", DEFAULT_USERNAME))
    name_ok = hmac.compare_digest(username.strip().casefold().encode(),
                                  stored_name.casefold().encode())
    return password_ok and name_ok


def password_acceptable(password) -> bool:
    return isinstance(password, str) and PASSWORD_MIN_LEN <= len(password) <= PASSWORD_MAX_LEN


def clean_username(username) -> str | None:
    """The name as stored, or None when it is not usable."""
    if not isinstance(username, str):
        return None
    name = username.strip()
    if not name or len(name) > USERNAME_MAX_LEN or any(ord(c) < 32 for c in name):
        return None
    return name


def origin_matches(origin: str | None, host: str) -> bool:
    """True when there is no Origin (not a cross-site browser request) or
    when it names the host the request was sent to."""
    if not origin:
        return True
    parts = urllib.parse.urlsplit(origin)
    return bool(parts.netloc) and parts.netloc.lower() == host.lower()


def mode_of(record: dict | None) -> str:
    if record is None:
        return MODE_UNSET
    return MODE_OPEN if record.get("open") is True else MODE_PASSWORD


def _load_record() -> dict | None:
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        # A broken file must not fall back to "unset" or "open": that would
        # let the next visitor in. It counts as a password nobody can match.
        log.error("Account file unreadable: %s", e)
        return {"broken": True}


def mode() -> str:
    return mode_of(_load_record())


def username() -> str:
    record = _load_record() or {}
    return str(record.get("user", DEFAULT_USERNAME)) if mode_of(record) == MODE_PASSWORD else ""


def generation() -> int:
    """Bumped with every change of the account, so the change ends every
    other session."""
    record = _load_record() or {}
    return int(record.get("generation", 0))


def _write(record: dict) -> None:
    record["generation"] = generation() + 1
    tmp = AUTH_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(record, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, AUTH_FILE)


def set_credentials(name: str, password: str) -> None:
    salt = secrets.token_bytes(SALT_BYTES)
    _write({"user": name, "salt": salt.hex(), "hash": hash_password(password, salt)})
    log.info("Account set for user %s", name)


def set_open() -> None:
    _write({"open": True})
    log.warning("Login switched off: anyone on the network can use the page")


def check_login(name, password) -> str:
    """'ok', 'wrong' or 'wait'. Slows down guessing without locking anyone
    out for good."""
    with _lock:
        if (_failures["count"] >= FAILURES_BEFORE_DELAY and
                time.monotonic() - _failures["last"] < FAILURE_DELAY_S):
            return "wait"
    record = _load_record()
    ok = (mode_of(record) == MODE_PASSWORD and isinstance(name, str)
          and isinstance(password, str) and verify(name, password, record))
    with _lock:
        if ok:
            _failures["count"] = 0
        else:
            _failures["count"] += 1
            _failures["last"] = time.monotonic()
    if not ok:
        log.warning("Login failed")
    return "ok" if ok else "wrong"


def session_key() -> bytes:
    """The key that signs session cookies, made once and kept."""
    try:
        return SESSION_KEY_FILE.read_bytes()
    except FileNotFoundError:
        key = secrets.token_bytes(SESSION_KEY_BYTES)
        fd = os.open(SESSION_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        return key
