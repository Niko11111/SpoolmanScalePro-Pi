"""The Pi's network: its name, which WLAN it is in, its own WLAN (hotspot).

Reading goes straight to nmcli and ip, which any user may call. Changing
goes through the root helper (host_actions.run_helper); its verbs and the
safety rules behind them are in system/host-helper.sh:
  - joining a WLAN falls back to the previous one when it fails,
  - the hotspot is only switched off when another network is there,
  - the setup WLAN opens at boot only when nothing else connected.

Parsing and input rules: network_rules.py.
"""

import logging
import socket
import subprocess

from . import network_rules as rules
from . import settings
from .host_actions import (EXIT_NO_OTHER_NETWORK, EXIT_WIFI_FAILED, NETWORK_TIMEOUT_S,
                           run_helper)
from .jobs import JobFailed, Progress

log = logging.getLogger(__name__)

# The connection names host-helper.sh gives its two access points.
HOTSPOT_CONNECTION = "spoolmanscale-hotspot"
SETUP_CONNECTION = "spoolmanscale-setup"
# Where the Pi is while it runs one of them (HOTSPOT_ADDRESS in the helper).
HOTSPOT_ADDRESS = "192.168.50.1"
QUERY_TIMEOUT_S = 10


def _read(cmd: list[str]) -> str | None:
    """The output of a read-only command, None when it is missing (a laptop)
    or failed."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=QUERY_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.info("%s not available: %s", cmd[0], e)
        return None
    return done.stdout if done.returncode == 0 else None


def status() -> dict:
    current = settings.load()
    base = {"hostname": socket.gethostname().split(".")[0],
            "hotspot_ssid": current["hotspot_ssid"], "hotspot_channel": current["hotspot_channel"],
            "hotspot_address": HOTSPOT_ADDRESS}
    active = _read(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
    if active is None:
        return {**base, "available": False}
    rows = rules.parse_active(active)
    addresses = rules.parse_ip_addresses(_read(["ip", "-4", "-o", "addr", "show", "scope", "global"]) or "")
    return {**base, "available": True,
            "wlan": rules.wlan_mode(rows, HOTSPOT_CONNECTION, SETUP_CONNECTION),
            "ethernet": any(r["type"] == "802-3-ethernet" for r in rows),
            "addresses": addresses}


def scan() -> list[dict] | None:
    result = run_helper("wifi-scan")
    return rules.parse_wifi_list(result.output) if result.ok else None


def set_hostname(name: str) -> bool:
    return run_helper("set-hostname", name).ok


def join_wifi(ssid: str, psk: str, progress: Progress) -> None:
    progress.step("joining_wifi")
    result = run_helper("wifi-connect", stdin_text=f"{ssid}\n{psk}\n", timeout_s=NETWORK_TIMEOUT_S)
    if result.code == EXIT_WIFI_FAILED:
        raise JobFailed("wifi_failed", ssid)
    if not result.ok:
        raise JobFailed("network_change_failed", "wifi-connect")
    progress.set_result(ssid=ssid)


def hotspot_on(ssid: str, psk: str, channel: int, progress: Progress) -> None:
    progress.step("starting_hotspot")
    # Kept for the form; the password stays with NetworkManager only.
    settings.update({"hotspot_ssid": ssid, "hotspot_channel": channel})
    result = run_helper("hotspot-on", stdin_text=f"{ssid}\n{psk}\n{channel}\n",
                        timeout_s=NETWORK_TIMEOUT_S)
    if not result.ok:
        raise JobFailed("network_change_failed", "hotspot-on")


def hotspot_off(progress: Progress) -> None:
    progress.step("stopping_hotspot")
    result = run_helper("hotspot-off", timeout_s=NETWORK_TIMEOUT_S)
    if result.code == EXIT_NO_OTHER_NETWORK:
        raise JobFailed("no_other_network")
    if not result.ok:
        raise JobFailed("network_change_failed", "hotspot-off")
