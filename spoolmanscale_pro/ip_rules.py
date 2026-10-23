"""The Pi's IPv4 address on its network: reading it from NetworkManager, and
checking an address the owner wants to fix it to. Pure, tested in
tests/test_ip_rules.py; the calls live in network.py, the change in the
root helper (verbs ip-check, ip-static, ip-dhcp).

A fixed address is not needed for this service to work: the scale and the
page use <name>.local. It helps devices that cannot resolve .local, and
anyone who entered the IP somewhere.
"""

import ipaddress

from .network_rules import split_terse


def parse_device_show(text: str) -> dict:
    """nmcli -t -f GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS device show
    <device>: the first address with its prefix, gateway, DNS servers, MAC."""
    values: dict[str, list[str]] = {}
    for line in text.splitlines():
        fields = split_terse(line)
        if len(fields) < 2 or not fields[1]:
            continue
        key = fields[0].split("[")[0]
        values.setdefault(key, []).append(":".join(fields[1:]))
    return {
        "address": (values.get("IP4.ADDRESS") or [""])[0],
        "gateway": (values.get("IP4.GATEWAY") or [""])[0],
        "dns": values.get("IP4.DNS", []),
        "mac": (values.get("GENERAL.HWADDR") or [""])[0],
    }


def check_static(address: str, current_cidr: str, gateway: str) -> str | None:
    """Why `address` cannot be this Pi's fixed address, or None.
    current_cidr: the address it has now with its prefix (192.168.4.20/24);
    the new one has to be in the same network, or the Pi would be cut off."""
    try:
        wanted = ipaddress.IPv4Address(address)
        network = ipaddress.IPv4Interface(current_cidr).network
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
        return "ip_invalid"
    if wanted not in network:
        return "ip_other_network"
    if wanted in (network.network_address, network.broadcast_address):
        return "ip_reserved"
    if gateway and str(wanted) == gateway:
        return "ip_is_gateway"
    if not wanted.is_private:
        return "ip_not_private"
    return None


def with_prefix(address: str, current_cidr: str) -> str:
    """192.168.4.50 and 192.168.4.20/24 -> 192.168.4.50/24."""
    return f"{address}/{ipaddress.IPv4Interface(current_cidr).network.prefixlen}"
