"""RAM, CPU temperature, SD card, uptime and clock of the Pi.

Read straight from /proc and /sys rather than through psutil: four small
files do not justify a compiled dependency. The parsers are pure and tested.
On a laptop without those files every value comes back as None, and the page
shows a dash.
"""

import logging
import shutil
import time
from pathlib import Path

log = logging.getLogger(__name__)

MEMINFO_FILE = Path("/proc/meminfo")
UPTIME_FILE = Path("/proc/uptime")
THERMAL_FILE = Path("/sys/class/thermal/thermal_zone0/temp")
ZRAM_DISKSIZE_FILE = Path("/sys/block/zram0/disksize")

KIB_PER_MIB = 1024
MILLIDEGREES_PER_DEGREE = 1000
BYTES_PER_MIB = 1024 * 1024
# Where the backends' volumes live, which is what fills up.
DISK_PATH = "/"


def parse_meminfo(text: str) -> dict | None:
    """Total and available RAM and swap in MiB. MemAvailable, not MemFree:
    the page cache counts as free for anything that asks."""
    values = {}
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[name.strip()] = int(parts[0]) // KIB_PER_MIB
    if "MemTotal" not in values or "MemAvailable" not in values:
        return None
    return {
        "ram_total_mib": values["MemTotal"],
        "ram_used_mib": values["MemTotal"] - values["MemAvailable"],
        "swap_total_mib": values.get("SwapTotal", 0),
        "swap_used_mib": values.get("SwapTotal", 0) - values.get("SwapFree", 0),
    }


def parse_uptime(text: str) -> int | None:
    try:
        return int(float(text.split()[0]))
    except (IndexError, ValueError):
        return None


def parse_millidegrees(text: str) -> float | None:
    try:
        return round(int(text.strip()) / MILLIDEGREES_PER_DEGREE, 1)
    except ValueError:
        return None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii")
    except OSError:
        return None


def _disk() -> dict | None:
    try:
        usage = shutil.disk_usage(DISK_PATH)
    except OSError as e:
        log.warning("Disk usage unreadable: %s", e)
        return None
    return {"disk_total_mib": usage.total // BYTES_PER_MIB,
            "disk_used_mib": usage.used // BYTES_PER_MIB}


def snapshot() -> dict:
    meminfo = _read(MEMINFO_FILE)
    uptime = _read(UPTIME_FILE)
    thermal = _read(THERMAL_FILE)
    return {
        "memory": parse_meminfo(meminfo) if meminfo else None,
        "disk": _disk(),
        "cpu_temp_c": parse_millidegrees(thermal) if thermal else None,
        "uptime_s": parse_uptime(uptime) if uptime else None,
        "zram": ZRAM_DISKSIZE_FILE.exists(),
        # Epoch seconds. The page compares it with the browser's clock and
        # offers to set the Pi's time when they are far apart: a Pi has no
        # battery-backed clock, and at a fair there is no network time.
        "clock_epoch_s": int(time.time()),
    }
