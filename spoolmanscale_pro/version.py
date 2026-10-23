"""The application version.

VERSION at the repository root is the one place it is written. The page
footer, the installer and the release workflow all read that file, and
scripts/check.sh fails when CHANGELOG.md has no entry for it.
"""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def read_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


APP_VERSION = read_version()
