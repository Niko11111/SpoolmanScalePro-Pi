"""RAM, CPU temperature, SD card, uptime and clock of the Pi.

Read straight from /proc and /sys rather than through psutil: four small
files do not justify a compiled dependency. The parsers are pure and tested.
On a laptop without those files every value comes back as None, and the page
shows a dash.
"""

import logging
import shutil
import subprocess
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
VCGENCMD_TIMEOUT_S = 5

# Bits of `vcgencmd get_throttled` (Raspberry Pi documentation, "vcgencmd").
# The low ones say what is happening now, the same ones 16 higher whether
# it happened since boot.
THROTTLE_BITS = {"under_voltage": 0, "freq_capped": 1, "throttled": 2, "soft_temp_limit": 3}
SINCE_BOOT_SHIFT = 16


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


def parse_throttled(text: str) -> dict | None:
    """'throttled=0x50005' -> {"now": [...], "since_boot": [...]}, the names
    of THROTTLE_BITS that are set. An under-voltage means the power supply
    or cable is too weak: the Pi slows down and the SD card can suffer."""
    _, _, value = text.strip().partition("=")
    try:
        bits = int(value, 16)
    except ValueError:
        return None
    return {"now": [n for n, b in THROTTLE_BITS.items() if bits >> b & 1],
            "since_boot": [n for n, b in THROTTLE_BITS.items() if bits >> (b + SINCE_BOOT_SHIFT) & 1]}


def _throttled() -> dict | None:
    """None where there is no vcgencmd (a laptop)."""
    try:
        done = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True,
                              timeout=VCGENCMD_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_throttled(done.stdout) if done.returncode == 0 else None


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
        "power": _throttled(),
        # Epoch seconds. The page compares it with the browser's clock and
        # offers to set the Pi's time when they are far apart: a Pi has no
        # battery-backed clock, and at a fair there is no network time.
        "clock_epoch_s": int(time.time()),
    }
