"""The service's one password, and the checks every request goes through.

First visit: the page asks for a password, which is stored as a scrypt hash
in AUTH_FILE. After that every /api route except the ones in
web/__init__.py's OPEN_ENDPOINTS needs a logged-in session (a signed cookie,
HttpOnly, SameSite=Lax).

Against requests from other sites (CSRF): a request that changes something
must carry the X-SSPro header, which a foreign page cannot set without a
CORS preflight this service never answers, and an Origin header, if present,
must name this host.

hash_password(), verify_password() and origin_matches() are pure and tested.
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

PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128
# scrypt cost: about 16 MiB and a tenth of a second on a Pi 3.
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16
SESSION_KEY_BYTES = 32

# After this many wrong passwords in a row, each further try waits.
FAILURES_BEFORE_DELAY = 5
FAILURE_DELAY_S = 30

CSRF_HEADER = "X-SSPro"

_lock = threading.Lock()
_failures = {"count": 0, "last": 0.0}


def hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N,
                            r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN)
    return digest.hex()


def verify_password(password: str, record: dict) -> bool:
    try:
        salt = bytes.fromhex(record["salt"])
        expected = record["hash"]
    except (KeyError, ValueError, TypeError):
        return False
    return hmac.compare_digest(hash_password(password, salt), expected)


def password_acceptable(password) -> bool:
    return isinstance(password, str) and PASSWORD_MIN_LEN <= len(password) <= PASSWORD_MAX_LEN


def origin_matches(origin: str | None, host: str) -> bool:
    """True when there is no Origin (not a cross-site browser request) or
    when it names the host the request was sent to."""
    if not origin:
        return True
    parts = urllib.parse.urlsplit(origin)
    return bool(parts.netloc) and parts.netloc.lower() == host.lower()


def _load_record() -> dict | None:
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        # A broken file must not fall back to "no password yet": that would
        # let the next visitor set one.
        log.error("Password file unreadable: %s", e)
        return {"broken": True}


def password_is_set() -> bool:
    return _load_record() is not None


def generation() -> int:
    """Bumped with every new password, so changing it ends every other
    session."""
    record = _load_record() or {}
    return int(record.get("generation", 0))


def set_password(password: str) -> None:
    salt = secrets.token_bytes(SALT_BYTES)
    record = {"salt": salt.hex(), "hash": hash_password(password, salt),
              "generation": generation() + 1}
    tmp = AUTH_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(record, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, AUTH_FILE)
    log.info("Password set")


def check_login(password: str) -> str:
    """'ok', 'wrong' or 'wait'. Slows down guessing without locking anyone
    out for good."""
    with _lock:
        if (_failures["count"] >= FAILURES_BEFORE_DELAY and
                time.monotonic() - _failures["last"] < FAILURE_DELAY_S):
            return "wait"
    record = _load_record()
    ok = record is not None and isinstance(password, str) and verify_password(password, record)
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
