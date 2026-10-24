"""The Pi's network: its name, which WLAN it is in, its own WLAN (hotspot).

Reading goes straight to nmcli and ip, which any user may call. Changing
goes through the root helper (host_actions.run_helper); its verbs and the
safety rules behind them are in system/host-helper.sh:
  - joining a WLAN falls back to the previous one when it fails,
  - the hotspot is only switched off when another network is there,
  - the setup WLAN opens at boot only when nothing else connected.

Parsing and input rules: network_rules.py, ip_rules.py (fixed address).
"""

import logging
import socket
import subprocess

from . import ip_rules
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


def primary_address() -> str | None:
    """The address the page header shows (network_rules.primary_address)."""
    return rules.primary_address(rules.parse_ip_addresses(
        _read(["ip", "-4", "-o", "addr", "show", "scope", "global"]) or ""))


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


# The fixed address (ip_rules.py). It applies to the connection the Pi is
# in the network through: the cable first, else the WLAN it joined; never
# its own hotspot, whose address is fixed anyway.
EXIT_GATEWAY_LOST = 3


def _uplink() -> dict | None:
    active = _read(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
    if active is None:
        return None
    rows = [r for r in rules.parse_active(active)
            if r["name"] not in (HOTSPOT_CONNECTION, SETUP_CONNECTION)
            and r["type"] in ("802-3-ethernet", "802-11-wireless")]
    rows.sort(key=lambda r: r["type"] != "802-3-ethernet")
    return rows[0] if rows else None


def ip_status() -> dict | None:
    """The uplink's address, gateway, DNS, MAC and whether it is fixed."""
    link = _uplink()
    if link is None:
        return None
    shown = _read(["nmcli", "-t", "-f", "GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                   "device", "show", link["device"]]) or ""
    method = _read(["nmcli", "-t", "-f", "ipv4.method", "connection", "show", link["name"]]) or ""
    return {"connection": link["name"], "device": link["device"],
            "fixed": method.strip().endswith(":manual"), **ip_rules.parse_device_show(shown)}


def check_address(address: str) -> str:
    """'free', 'taken', or a reason from ip_rules.check_static."""
    current = ip_status()
    if current is None or not current["address"]:
        return "ip_no_uplink"
    refusal = ip_rules.check_static(address, current["address"], current["gateway"])
    if refusal:
        return refusal
    if address == current["address"].split("/")[0]:
        return "free"  # its own address: nobody else answers for it
    result = run_helper("ip-check", address, current["device"])
    return result.output.strip() if result.ok else "ip_check_failed"


def fix_address(address: str, progress: Progress) -> None:
    progress.step("checking_address")
    verdict = check_address(address)
    if verdict != "free":
        raise JobFailed("ip_taken" if verdict == "taken" else verdict, address)
    current = ip_status()
    dns = ",".join(current["dns"]) or current["gateway"]
    progress.step("fixing_address")
    progress.set_result(address=address)
    result = run_helper("ip-static", current["connection"], ip_rules.with_prefix(address, current["address"]),
                        current["gateway"], dns, timeout_s=NETWORK_TIMEOUT_S)
    if result.code == EXIT_GATEWAY_LOST:
        raise JobFailed("ip_reverted", address)
    if not result.ok:
        raise JobFailed("network_change_failed", "ip-static")


def address_from_router(progress: Progress) -> None:
    current = ip_status()
    if current is None:
        raise JobFailed("ip_no_uplink")
    progress.step("fixing_address")
    if not run_helper("ip-dhcp", current["connection"], timeout_s=NETWORK_TIMEOUT_S).ok:
        raise JobFailed("network_change_failed", "ip-dhcp")
