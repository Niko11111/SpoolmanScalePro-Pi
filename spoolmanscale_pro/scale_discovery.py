"""Finding SpoolmanScales on the network by mDNS, so nobody has to type an
address.

A scale announces its web interface as _http._tcp with these TXT entries
(firmware src/services/mdns_service.cpp): model=WT32-SC01-Plus, fw, id and
backend. avahi-browse lists every _http._tcp service; parse_avahi() keeps
the ones that carry the scale's model and reads them. It is pure and
tested; discover() runs avahi-browse, which only the Pi has (avahi-utils).
"""

import logging
import re
import subprocess

log = logging.getLogger(__name__)

# The models a SpoolmanScale firmware announces itself with.
SCALE_MODELS = ("WT32-SC01-Plus",)
BROWSE_TIMEOUT_S = 10
_ESCAPE_RE = re.compile(r"\\(\d{3})")


def _unescape(text: str) -> str:
    """avahi writes a space in a name as \\032 and so on (decimal)."""
    return _ESCAPE_RE.sub(lambda m: chr(int(m.group(1))), text)


def _txt(field: str) -> dict:
    """ "fw=v0.8.3" "model=WT32-SC01-Plus" -> {"fw": "v0.8.3", ...}"""
    entries = {}
    for item in re.findall(r'"([^"]*)"', field):
        key, sep, value = item.partition("=")
        if sep:
            entries[key] = value
    return entries


def parse_avahi(text: str) -> list[dict]:
    """avahi-browse -rpt output: one entry per scale (by its id), IPv4
    preferred, sorted by name."""
    found: dict[str, dict] = {}
    for line in text.splitlines():
        fields = line.split(";")
        if len(fields) < 10 or fields[0] != "=":
            continue
        txt = _txt(";".join(fields[9:]))
        if txt.get("model") not in SCALE_MODELS:
            continue
        key = txt.get("id") or fields[7]
        entry = {"name": _unescape(fields[3]), "host": fields[6], "address": fields[7],
                 "port": int(fields[8]) if fields[8].isdigit() else 80,
                 "id": txt.get("id", ""), "firmware": txt.get("fw", ""), "backend": txt.get("backend", "")}
        known = found.get(key)
        if known is None or (fields[2] == "IPv4" and ":" in known["address"]):
            found[key] = entry
    return sorted(found.values(), key=lambda e: e["name"].lower())


def discover() -> list[dict] | None:
    """The scales on the network, or None when avahi-browse is missing."""
    try:
        done = subprocess.run(["avahi-browse", "--resolve", "--parsable", "--terminate", "_http._tcp"],
                              capture_output=True, text=True, timeout=BROWSE_TIMEOUT_S)
    except FileNotFoundError:
        log.info("avahi-browse not installed: no scale discovery")
        return None
    except subprocess.TimeoutExpired as e:
        log.warning("avahi-browse took longer than %d s", BROWSE_TIMEOUT_S)
        return parse_avahi(e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
    return parse_avahi(done.stdout)
