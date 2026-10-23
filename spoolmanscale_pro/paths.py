"""Where things live on disk. Every path the service reads or writes is named
here and nowhere else.

The code itself is read-only to the service (an installed release under
/opt/spoolmanscale-pro). Everything it writes goes under DATA_DIR, which
SSPRO_DATA_DIR overrides for development on a laptop.
"""

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("SSPRO_DATA_DIR", "/var/lib/spoolmanscale-pro"))

COMPOSE_FILE = APP_ROOT / "compose" / "docker-compose.yml"
TEMPLATE_DIR = APP_ROOT / "templates"
STATIC_DIR = APP_ROOT / "static"

SETTINGS_FILE = DATA_DIR / "settings.json"
AUTH_FILE = DATA_DIR / "auth.json"
# Logins this Pi gives the backends it starts (backend_secrets.py).
SECRETS_FILE = DATA_DIR / "backend-secrets.json"
SESSION_KEY_FILE = DATA_DIR / "session.key"
BACKUP_DIR = DATA_DIR / "backups"
DEMO_SNAPSHOT_DIR = DATA_DIR / "demo-snapshot"
# Demo mode is on while this file exists. Deliberately no switch on the page:
# it is meant for one demo kit, not for every installation.
DEMO_FLAG_FILE = DATA_DIR / "demo-enabled"

# The host's own time zone, handed to the backend containers so their
# timestamps match the Pi. Debian keeps the name in this file.
HOST_TIMEZONE_FILE = Path("/etc/timezone")


def ensure_data_dirs() -> None:
    """Creates the data directories. Private to the service user: the
    settings file holds the scale's web password."""
    for d in (DATA_DIR, BACKUP_DIR, DEMO_SNAPSHOT_DIR):
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
