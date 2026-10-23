"""The backup file: what it is called, what is inside, and whether an
uploaded one may be restored.

A backup is a plain tar file with two members:
  meta.json     which backend, which image version, when, by which version
                of this service
  data.tar.gz   the backend's data directory, as tar inside its container
                packed it (docker_compose.archive_volume)

Everything here works on files and bytes only, no Docker and no network,
and is tested in tests/test_archive_format.py.
"""

import io
import json
import re
import tarfile
from datetime import datetime
from pathlib import Path

FORMAT_VERSION = 1
META_NAME = "meta.json"
DATA_NAME = "data.tar.gz"
META_MAX_BYTES = 64 * 1024

# What a data archive may hold. The backends' data are a database, logs and
# a few folders of images or print files; a hundred thousand entries or
# 8 GiB unpacked is not a backup of that, it is something else.
DATA_MAX_MEMBERS = 100_000
DATA_MAX_UNPACKED_BYTES = 8 * 1024 ** 3

# Why a backup was made, when not by hand: it ends up in the name.
REASONS = ("before-restore", "before-update", "auto")
# <backend>_<YYYY-MM-DD_HHMMSS>[_<reason>].tar
NAME_RE = re.compile(r"^([a-z]+)_(\d{4}-\d{2}-\d{2}_\d{6})(?:_(" + "|".join(REASONS) + r"))?\.tar$")
TIME_FORMAT = "%Y-%m-%d_%H%M%S"


class ArchiveError(Exception):
    """An archive that must not be restored. code is what the page shows:
    archive_unreadable, archive_wrong_format, archive_unsafe, archive_too_big."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def backup_name(key: str, when: datetime, reason: str | None = None) -> str:
    """reason: one of REASONS, or None for a backup made by hand."""
    if reason is not None and reason not in REASONS:
        raise ValueError(f"unknown backup reason {reason}")
    suffix = f"_{reason}" if reason else ""
    return f"{key}_{when.strftime(TIME_FORMAT)}{suffix}.tar"


def parse_backup_name(name: str) -> dict | None:
    """The parts of a name this service gave, or None for any other name.
    The one gate a file name from a request passes before it touches disk."""
    match = NAME_RE.match(name)
    if not match:
        return None
    try:
        when = datetime.strptime(match.group(2), TIME_FORMAT)
    except ValueError:
        return None
    return {"backend": match.group(1), "created": when.isoformat(timespec="seconds"),
            "reason": match.group(3) or ""}


def make_meta(key: str, image: str, app_version: str, when: datetime) -> dict:
    return {"format": FORMAT_VERSION, "backend": key, "image": image,
            "app_version": app_version, "created": when.isoformat(timespec="seconds")}


def write_bundle(dest: Path, meta: dict, data_file: Path) -> None:
    with tarfile.open(dest, "w") as bundle:
        raw = json.dumps(meta, indent=2).encode("utf-8")
        info = tarfile.TarInfo(META_NAME)
        info.size = len(raw)
        info.mtime = int(datetime.now().timestamp())
        bundle.addfile(info, io.BytesIO(raw))
        bundle.add(data_file, arcname=DATA_NAME)


def read_meta(bundle_path: Path) -> dict:
    try:
        with tarfile.open(bundle_path, "r:") as bundle:
            member = bundle.getmember(META_NAME)
            if member.size > META_MAX_BYTES:
                raise ArchiveError("archive_wrong_format", "meta.json too large")
            meta = json.loads(bundle.extractfile(member).read())
            bundle.getmember(DATA_NAME)
    except ArchiveError:
        raise
    except KeyError as e:
        raise ArchiveError("archive_wrong_format", str(e)) from e
    except (tarfile.TarError, OSError, json.JSONDecodeError, AttributeError) as e:
        raise ArchiveError("archive_unreadable", str(e)) from e
    if not isinstance(meta, dict) or meta.get("format") != FORMAT_VERSION or \
            not isinstance(meta.get("backend"), str):
        raise ArchiveError("archive_wrong_format", "unknown meta.json")
    return meta


def extract_data(bundle_path: Path, dest: Path) -> None:
    """Copies data.tar.gz out of the bundle to dest, unchanged."""
    try:
        with tarfile.open(bundle_path, "r:") as bundle, open(dest, "wb") as out:
            source = bundle.extractfile(DATA_NAME)
            while chunk := source.read(1024 * 1024):
                out.write(chunk)
    except (tarfile.TarError, OSError, KeyError, AttributeError) as e:
        raise ArchiveError("archive_unreadable", str(e)) from e


def _member_is_safe(member: tarfile.TarInfo) -> bool:
    name = member.name
    parts = Path(name).parts
    if name.startswith("/") or ".." in parts:
        return False
    # Files and folders only. A link could point the restore anywhere in
    # the container; the backends' data have none.
    return member.isfile() or member.isdir()


def _scan(data: tarfile.TarFile) -> int:
    """Walks every entry once; returns how many there were."""
    count = total = 0
    for member in data:
        count += 1
        total += max(member.size, 0)
        if not _member_is_safe(member):
            raise ArchiveError("archive_unsafe", member.name)
        if count > DATA_MAX_MEMBERS or total > DATA_MAX_UNPACKED_BYTES:
            raise ArchiveError("archive_too_big", f"{count} entries, {total} bytes")
    return count


def check_data_archive(data_path: Path) -> None:
    """Raises ArchiveError unless every entry is a plain file or folder
    inside the data directory and the whole stays within the limits.
    Reads the archive once, as a stream, without unpacking anything."""
    try:
        with tarfile.open(data_path, "r|gz") as data:
            count = _scan(data)
    except ArchiveError:
        raise
    except (tarfile.TarError, OSError, EOFError) as e:
        raise ArchiveError("archive_unreadable", str(e)) from e
    if count == 0:
        raise ArchiveError("archive_wrong_format", "data archive is empty")
