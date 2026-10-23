"""Reading NetworkManager's answers and checking what a person typed for a
network. Pure functions, tested in tests/test_network_rules.py; the calls
to nmcli and to the root helper live in network.py.

nmcli is always called with -t (terse): fields separated by ":", and a ":"
or "\\" inside a value escaped with a backslash.
"""

import re

# RFC 1123: one label of letters, digits and hyphens, not starting or ending
# with a hyphen. No underscore: mDNS would publish it, but many resolvers
# and routers refuse it.
HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
SSID_MAX_BYTES = 32
PSK_MIN_LEN = 8
PSK_MAX_LEN = 63
# 2.4 GHz channels that do not overlap; the scale's ESP32 has no 5 GHz.
HOTSPOT_CHANNELS = (1, 6, 11)


def split_terse(line: str) -> list[str]:
    """One line of nmcli -t output into its fields, escapes resolved."""
    fields, current, escaped = [], [], False
    for ch in line:
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
    fields.append("".join(current))
    return fields


def _scan_row(fields: list[str]) -> dict | None:
    if len(fields) < 5:
        return None
    in_use, ssid, signal, security, channel = fields[:5]
    if not ssid:
        return None  # a hidden network: it can only be joined by name
    return {
        "ssid": ssid,
        "signal": int(signal) if signal.isdigit() else 0,
        "secure": security not in ("", "--"),
        "channel": int(channel) if channel.isdigit() else None,
        "in_use": in_use.strip() == "*",
    }


def parse_wifi_list(text: str) -> list[dict]:
    """nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY,CHAN device wifi list.
    One row per network name, the strongest access point of it, strongest
    network first."""
    best: dict[str, dict] = {}
    for line in text.splitlines():
        row = _scan_row(split_terse(line))
        if row is None:
            continue
        known = best.get(row["ssid"])
        if known is None or row["signal"] > known["signal"]:
            row["in_use"] = row["in_use"] or bool(known and known["in_use"])
            best[row["ssid"]] = row
        elif row["in_use"]:
            known["in_use"] = True
    return sorted(best.values(), key=lambda r: r["signal"], reverse=True)


def parse_active(text: str) -> list[dict]:
    """nmcli -t -f NAME,TYPE,DEVICE connection show --active."""
    rows = []
    for line in text.splitlines():
        fields = split_terse(line)
        if len(fields) >= 3 and fields[2]:
            rows.append({"name": fields[0], "type": fields[1], "device": fields[2]})
    return rows


def valid_hostname(name) -> bool:
    return isinstance(name, str) and bool(HOSTNAME_RE.match(name))


def valid_ssid(ssid) -> bool:
    if not isinstance(ssid, str) or not ssid or "\n" in ssid or "\r" in ssid:
        return False
    return len(ssid.encode("utf-8")) <= SSID_MAX_BYTES


def valid_psk(psk, allow_empty: bool) -> bool:
    """WPA2 wants 8 to 63 characters. Empty is an open network, which a
    client may join but the hotspot never offers."""
    if psk == "" and allow_empty:
        return True
    return isinstance(psk, str) and PSK_MIN_LEN <= len(psk) <= PSK_MAX_LEN \
        and "\n" not in psk and "\r" not in psk


def valid_channel(channel) -> bool:
    return isinstance(channel, int) and not isinstance(channel, bool) and channel in HOTSPOT_CHANNELS


def parse_ip_addresses(text: str) -> dict[str, str]:
    """ip -4 -o addr show scope global: interface -> its IPv4 address."""
    addresses = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "inet":
            addresses.setdefault(parts[1], parts[3].split("/")[0])
    return addresses


def wlan_mode(active: list[dict], hotspot: str, setup: str) -> dict:
    """What wlan0 does right now, from the active connections: "hotspot"
    (the Pi's own WLAN), "setup" (the fallback WLAN), "client" (joined a
    network, named in connection) or "off"."""
    wlan = next((r for r in active if r["device"] == "wlan0"), None)
    if wlan is None:
        return {"mode": "off", "connection": ""}
    if wlan["name"] == hotspot:
        return {"mode": "hotspot", "connection": wlan["name"]}
    if wlan["name"] == setup:
        return {"mode": "setup", "connection": wlan["name"]}
    return {"mode": "client", "connection": wlan["name"]}
