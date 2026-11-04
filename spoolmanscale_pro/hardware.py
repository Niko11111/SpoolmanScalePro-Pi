"""What this Pi can carry: one backend at a time, or several.

Three sizes by RAM, decided with Nikolai on 23.10.2026:
  small   under 900 MB (Pi Zero 2 W): one backend at a time, switching only.
          Spoolman recommended; FilaMan and BamBuddy run, but slowly (both
          were sluggish on a Zero, and BamBuddy does not recommend it), so
          they come with a warning.
  medium  under 1900 MB (Pi 3): several at once, after a warning with the
          numbers.
  large   2 GB and more (Pi 4, Pi 5): several at once, no questions.
On small and medium Pis every backend gets a memory limit, so one that grows
cannot freeze the whole Pi; it is twice its typical use, at most what the
Pi has to spare. The limit is on RAM only: swapping to zram stays allowed,
so a backend that needs more gets slow instead of killed, and the Pi stays
usable (compose memswap_limit -1). Those limits need the kernel's memory
controller, which a Pi 3 boots without (cgroup_disable=memory): there they
are set but have no effect.

The rules and the budget are pure functions, tested in tests/test_hardware.py.
"""

from pathlib import Path

from .backends import BACKENDS, Backend, backend_by_key

MODEL_FILE = Path("/proc/device-tree/model")
MEMINFO_FILE = Path("/proc/meminfo")
KIB_PER_MIB = 1024

SMALL_BELOW_MB = 900
LARGE_FROM_MB = 1900
# What Raspberry Pi OS Lite, Docker and this service take before any
# backend: measured on a Pi 3 with no backend running (24.10.2026). Not yet
# measured on a Zero 2 W.
SYSTEM_RESERVE_MB = 271
MEMORY_LIMIT_FACTOR = 2
RECOMMENDED_ON_SMALL = ("spoolman",)
# FilaMan's worker processes (WEB_CONCURRENCY, FilaMan 1.6.1 and newer). Each
# holds a full copy of the app. The registry's typical_ram_mb is for the
# standard count; one worker with a printer driver was measured at 190 MB,
# so each one less takes this much off, which leaves about 200 MB for one.
FILAMAN_WORKERS_STANDARD = 4
FILAMAN_WORKERS_ON_A_SMALL_PI = 1
FILAMAN_WORKER_CHOICES = (1, 2, 3, 4)
FILAMAN_RAM_PER_WORKER_MB = 93


def size_of(ram_mb: int, model: str = "") -> str:
    """The model decides where it is known: the RAM a Pi reports depends on
    how much the GPU takes (a Pi 3 with gpu_mem=128 reports about 860 MB)."""
    if "Zero" in model:
        return "small"
    if model.startswith("Raspberry Pi 3"):
        return "medium"
    if ram_mb < SMALL_BELOW_MB:
        return "small"
    return "medium" if ram_mb < LARGE_FROM_MB else "large"


def rules(ram_mb: int, model: str = "") -> dict:
    """What the page offers on a Pi with this much RAM."""
    size = size_of(ram_mb, model)
    return {
        "size": size,
        "parallel": {"small": "blocked", "medium": "warn", "large": "free"}[size],
        "memory_limits": size != "large",
        "parallel_default": size == "large",
        "slow_backends": [b.key for b in BACKENDS if size == "small" and b.key not in RECOMMENDED_ON_SMALL],
    }


def filaman_workers(ram_mb: int, model: str = "", choice: int | None = None) -> int:
    """How many workers FilaMan starts: the owner's choice, or else one on a
    Pi smaller than a Pi 4. There one worker is enough for a scale and a
    browser, and it never has to forward a request to the printer drivers."""
    if choice is not None:
        return choice
    return FILAMAN_WORKERS_STANDARD if size_of(ram_mb, model) == "large" else FILAMAN_WORKERS_ON_A_SMALL_PI


def typical_ram_mb(backend: Backend, workers: int = FILAMAN_WORKERS_STANDARD) -> int:
    """A backend's typical use; only FilaMan's depends on its workers."""
    if backend.key != "filaman":
        return backend.typical_ram_mb
    return backend.typical_ram_mb - (FILAMAN_WORKERS_STANDARD - workers) * FILAMAN_RAM_PER_WORKER_MB


def budget(ram_mb: int, running: list[str], adding: str, workers: int = FILAMAN_WORKERS_STANDARD) -> dict:
    """RAM after starting `adding` next to `running`, from the backends'
    typical use (backends.py). fits: it stays within what the Pi has."""
    keys = sorted(set(running) | {adding})
    needed = SYSTEM_RESERVE_MB + sum(typical_ram_mb(backend_by_key(k), workers) for k in keys)
    return {"after_mb": needed, "total_mb": ram_mb, "fits": needed <= ram_mb}


def memory_limits(ram_mb: int, model: str = "", workers: int = FILAMAN_WORKERS_STANDARD) -> dict[str, int]:
    """Backend key -> limit in MB, or nothing on a large Pi. Never below the
    backend's typical use: less would only make it swap from the start."""
    if not rules(ram_mb, model)["memory_limits"]:
        return {}
    spare = ram_mb - SYSTEM_RESERVE_MB
    limits = {}
    for b in BACKENDS:
        typical = typical_ram_mb(b, workers)
        limits[b.key] = max(typical, min(typical * MEMORY_LIMIT_FACTOR, spare))
    return limits


def parse_meminfo_total(text: str) -> int | None:
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) // KIB_PER_MIB
    return None


def detect() -> dict:
    """Model and RAM of this machine. A laptop counts as large."""
    try:
        model = MODEL_FILE.read_bytes().decode("ascii", "replace").strip("\x00 \n")
    except OSError:
        model = ""
    try:
        ram_mb = parse_meminfo_total(MEMINFO_FILE.read_text(encoding="ascii"))
    except OSError:
        ram_mb = None
    return {"model": model, "ram_mb": ram_mb or 0, "is_pi": model.startswith("Raspberry Pi")}


def effective_ram_mb(found: dict) -> int:
    """The RAM the rules are made from; on a machine that is not a Pi (a
    developer's laptop) everything is allowed."""
    return found["ram_mb"] if found["is_pi"] and found["ram_mb"] else 1 << 20
