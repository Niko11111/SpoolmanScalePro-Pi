"""The inventory backends this Pi can run, as plain data.

One entry per backend. The key is also the service name and the profile in
compose/docker-compose.yml; tests/test_backends.py holds the two together.
The image and its version live in the compose file only.

scale_mode is the number the scale uses for the backend (BackendMode in the
firmware's services/backend.h), scale_name what its /status.json reports
for it (backendModeName() there).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Backend:
    key: str
    label: str
    scale_mode: int
    scale_name: str
    port: int
    health_path: str
    # The directory inside the container that holds the backend's whole
    # state. A backup archives exactly this, a restore replaces it.
    data_dir: str
    homepage: str
    # Where updates are looked for. image is the repository on ghcr.io, the
    # same one compose/docker-compose.yml pulls from (tests/test_backends.py
    # holds the two together); github the project whose releases carry the
    # change notes; version_env the compose variable that picks the version.
    image: str
    github: str
    version_env: str
    # Typical RAM in use, measured on a busy server (23.10.2026) with some
    # room on top. The base of the budget in hardware.py.
    typical_ram_mb: int
    # Top-level entries of data_dir a backup leaves out and a restore leaves
    # alone: the backend's own backups, which would otherwise ride along in
    # every archive and make each one larger than the last.
    archive_skip: tuple[str, ...] = ()


BACKENDS = (
    Backend(
        key="spoolman",
        label="Spoolman",
        scale_mode=0,
        scale_name="Spoolman",
        port=7912,
        health_path="/api/v1/health",
        data_dir="/home/app/.local/share/spoolman",
        homepage="https://github.com/Donkie/Spoolman",
        image="donkie/spoolman",
        github="Donkie/Spoolman",
        version_env="SPOOLMAN_VERSION",
        typical_ram_mb=180,
        archive_skip=("backups",),
    ),
    Backend(
        key="filaman",
        label="FilaMan",
        scale_mode=1,
        scale_name="FilaMan",
        port=8002,
        health_path="/health",
        data_dir="/app/data",
        homepage="https://filaman.app",
        image="fire-devils/filaman-system",
        github="Fire-Devils/filaman-system",
        version_env="FILAMAN_VERSION",
        typical_ram_mb=480,
        archive_skip=("backups",),
    ),
    Backend(
        key="bambuddy",
        label="BamBuddy",
        scale_mode=2,
        scale_name="BamBuddy",
        port=8000,
        health_path="/health",
        data_dir="/app/data",
        homepage="https://github.com/maziggy/bambuddy",
        image="maziggy/bambuddy",
        github="maziggy/bambuddy",
        version_env="BAMBUDDY_VERSION",
        typical_ram_mb=420,
        archive_skip=("backups",),
    ),
)

BACKEND_KEYS = tuple(b.key for b in BACKENDS)


def backend_by_key(key: str) -> Backend | None:
    for b in BACKENDS:
        if b.key == key:
            return b
    return None
