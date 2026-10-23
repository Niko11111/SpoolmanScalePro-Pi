"""Giving the scale its credentials for FilaMan and BamBuddy from here,
instead of typing them on the scale's small screen.

FilaMan: this Pi logs in to the FilaMan it runs (with the admin login it
made, backend_secrets.py, or one the owner types in once and that is not
kept), makes an API key and a device, logs out, then has the scale register
itself with the device code and gives it the key. FilaMan must be the
backend running here, because the scale registers itself at its server.
Each run makes a new key and device in FilaMan; old ones can be deleted
there.

BamBuddy needs a key only when its login is switched on; the owner pastes
one made in BamBuddy's settings and it is passed on.
"""

import logging

from . import backend_secrets, docker_compose, health, settings, switcher
from .backends import backend_by_key
from .filaman_admin import FilamanAdmin, FilamanError
from .jobs import JobFailed, Progress
from .scale_api import ScaleClient, ScaleError
from .scale_setup import switch_scale

log = logging.getLogger(__name__)

FILAMAN = backend_by_key("filaman")


def _client() -> ScaleClient:
    current = settings.load()
    if not current["scale_address"]:
        raise JobFailed("scale_not_paired")
    return ScaleClient(current["scale_address"], current["scale_password"])


def _filaman_credentials(progress: Progress, email: str | None, password: str | None) -> tuple[str, str]:
    """From FilaMan: an API key and a device code, made with the given login
    or else the one this Pi made."""
    if settings.load()["active_backend"] != "filaman" or \
            (docker_compose.states() or {}).get("filaman") != "running":
        raise JobFailed("filaman_not_active")
    if not email:
        stored = backend_secrets.filaman_admin()
        email, password = stored["email"], stored["password"]
    progress.step("filaman_login")
    admin = FilamanAdmin(health.backend_url(FILAMAN))
    admin.login(email, password or "")
    try:
        return admin.create_api_key(), admin.create_device()
    finally:
        admin.logout()


def connect_filaman(email: str | None, password: str | None, progress: Progress) -> None:
    client = _client()
    try:
        key, code = _filaman_credentials(progress, email, password)
        switch_scale(client, FILAMAN)
        progress.step("scale_register")
        client.filaman_register(code)
        client.set_filaman_key(key)
    except (FilamanError, ScaleError) as e:
        raise JobFailed(e.code, str(e)) from e
    log.info("Scale registered at FilaMan and given an API key")
    switcher.tell_scale(FILAMAN, progress)


def send_bambuddy_key(key: str) -> None:
    """Raises ScaleError when the scale refuses it."""
    current = settings.load()
    ScaleClient(current["scale_address"], current["scale_password"]).set_bambuddy_key(key)
