"""Reading apt's answers for the Raspberry Pi OS update. Pure, tested in
tests/test_os_update_rules.py; the calls live in os_update.py.

The search runs `apt-get -s full-upgrade` (simulate, install nothing).
full-upgrade rather than upgrade because Raspberry Pi OS ships kernel and
firmware as packages that need it; plain upgrade would hold them back.
The parsing follows TheRentalScale's trs_system_update.py, where it has
been in use since 03.09.2026.
"""

import re

# Inst libfoo [1.2.3-1] (1.2.4-1 Debian:12/stable [arm64])
# Inst new-package (1.0-1 Debian:12/stable [arm64])    <- not installed yet
_INST_RE = re.compile(r"^Inst\s+(?P<name>\S+)(?:\s+\[(?P<current>[^\]]+)\])?\s+\((?P<candidate>\S+)")
# Remv old-package [1.0-1]
_REMV_RE = re.compile(r"^Remv\s+(?P<name>\S+)")
# 3 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
_SUMMARY_RE = re.compile(r"^(?P<upgraded>\d+)\s+upgraded,\s+(?P<installed>\d+)\s+newly installed,"
                         r"\s+(?P<removed>\d+)\s+to remove")
# The last line the helper's units (OS upgrade, self-update, Tailscale)
# write to their logs.
_EXIT_RE = re.compile(r"^SSPRO-EXIT:(\d+)$", re.M)
# Packages whose new version only takes effect after a restart.
_REBOOT_PACKAGE_RE = re.compile(r"^(linux-image|raspi-firmware|raspberrypi-kernel|raspberrypi-bootloader|linux-modules)")


def parse_packages(apt_output: str) -> list[dict]:
    """Packages an upgrade would install, in apt's order. Unknown lines are
    skipped: apt writes progress, warnings and Conf lines in between."""
    rows = []
    for line in (apt_output or "").splitlines():
        match = _INST_RE.match(line.strip())
        if match:
            rows.append({"name": match.group("name"), "current": match.group("current"),
                         "candidate": match.group("candidate")})
    return rows


def parse_removals(apt_output: str) -> list[str]:
    return [m.group("name") for line in (apt_output or "").splitlines()
            if (m := _REMV_RE.match(line.strip()))]


def parse_summary(apt_output: str) -> dict | None:
    for line in (apt_output or "").splitlines():
        match = _SUMMARY_RE.match(line.strip())
        if match:
            return {"upgraded": int(match.group("upgraded")),
                    "newly_installed": int(match.group("installed")),
                    "removed": int(match.group("removed"))}
    return None


def build_result(apt_output: str) -> dict:
    """The search result for the page. mismatch: the package list and apt's
    own count differ, so the list missed a line format; the page then shows
    apt's number instead of presenting a short list as complete."""
    packages = parse_packages(apt_output)
    summary = parse_summary(apt_output)
    expected = summary["upgraded"] + summary["newly_installed"] if summary else None
    return {
        "packages": packages,
        "removals": parse_removals(apt_output),
        "summary": summary,
        "mismatch": summary is not None and expected != len(packages),
        "restart_after": any(_REBOOT_PACKAGE_RE.match(p["name"]) for p in packages),
    }


def exit_code(log_text: str) -> int | None:
    """The upgrade's exit code from its log, None while it has not ended."""
    found = _EXIT_RE.findall(log_text or "")
    return int(found[-1]) if found else None


def log_lines(text: str) -> list[str]:
    """A log as the page shows it: no blank lines, no exit marker."""
    return [line for line in (text or "").splitlines() if line.strip() and not _EXIT_RE.match(line)]


def _flavor(release: str) -> str:
    """6.6.51+rpt-rpi-v8 -> +rpt-rpi-v8. Raspberry Pi OS installs several
    kernel flavours side by side (rpi-v8, rpi-2712 for the Pi 5); only
    kernels of the running flavour count."""
    return re.sub(r"^[\d.]+", "", release)


def _version_key(release: str) -> tuple:
    match = re.match(r"^[\d.]+", release)
    return tuple(int(p) for p in match.group(0).split(".") if p) if match else ()


def kernel_restart_needed(running: str, installed: list[str]) -> bool:
    """True when the update only takes effect after a restart: the running
    kernel's modules are gone, or a newer kernel of its flavour is there.
    installed: the directory names under /lib/modules (none on a laptop)."""
    if not installed:
        return False
    if running not in installed:
        return True
    same = [k for k in installed if _flavor(k) == _flavor(running)]
    return max(same, key=_version_key) != running
