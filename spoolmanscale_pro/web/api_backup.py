"""/api/backups: create, list, download, delete, restore, upload."""

import logging
import secrets

from flask import Blueprint, request, send_file

from .. import backups
from ..archive_format import parse_backup_name
from ..backends import backend_by_key
from ..jobs import RUNNER
from ..paths import BACKUP_DIR
from .responses import fail, ok

log = logging.getLogger(__name__)

bp = Blueprint("api_backup", __name__, url_prefix="/api/backups")


def _start(kind: str, key: str, fn):
    job = RUNNER.start(kind, key, fn)
    if job is None:
        return fail("busy", 409)
    return ok(202, job=job)


@bp.get("")
def overview():
    return ok(backups=backups.list_backups())


@bp.post("/<key>")
def create(key):
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    return _start("backup", key, lambda progress: backups.create(backend, progress))


@bp.get("/file/<name>")
def download(name):
    path = backups.path_of(name)
    if path is None:
        return fail("not_found", 404)
    return send_file(path, mimetype="application/x-tar", as_attachment=True, download_name=name)


@bp.delete("/file/<name>")
def delete(name):
    path = backups.path_of(name)
    if path is None:
        return fail("not_found", 404)
    # The running job may be restoring from exactly this file.
    if RUNNER.busy():
        return fail("busy", 409)
    path.unlink(missing_ok=True)
    log.info("Backup deleted: %s", name)
    return ok()


@bp.post("/file/<name>/restore")
def restore(name):
    path = backups.path_of(name)
    if path is None:
        return fail("not_found", 404)
    backend = backend_by_key(parse_backup_name(name)["backend"])
    if backend is None:
        return fail("unknown_backend", 404)
    return _start("restore", backend.key, lambda progress: backups.restore(backend, path, progress))


@bp.post("/upload/<key>")
def upload(key):
    """Restores a backup file from this device. It is checked before
    anything is touched, and removed again afterwards."""
    backend = backend_by_key(key)
    if backend is None:
        return fail("unknown_backend", 404)
    if RUNNER.busy():
        return fail("busy", 409)
    sent = request.files.get("file")
    if sent is None:
        return fail("no_file")
    path = BACKUP_DIR / f"upload-{secrets.token_hex(8)}.upload"
    sent.save(path)

    def run(progress):
        try:
            backups.restore(backend, path, progress)
        finally:
            path.unlink(missing_ok=True)

    response = _start("restore", key, run)
    if response[1] != 202:
        path.unlink(missing_ok=True)
    return response
