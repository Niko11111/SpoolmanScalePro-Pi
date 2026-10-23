"""Talks to a SpoolmanScale's web interface.

Two routes of the firmware are used, nothing else:

  GET  /status.json        which backend the scale uses, at which address,
                           and whether it reached it (web/pages/page_status.cpp)
  POST /api/backend/mode   body "0", "1" or "2": switch the backend
                           (web/pages/page_backend.cpp)

The scale keeps one address per backend, so switching the mode is all it
takes once each address has been entered on the scale. The second route sits
behind the scale's "settings" share, and behind its web password when one is
set: that password goes along as HTTP Basic auth.

The firmware checks the Host header against its own names and refuses a
foreign Origin. A request from here carries the scale's own address as Host
and no Origin, which is what those checks expect from a non-browser client.
"""

import base64
import json
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from .backends import Backend

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 5
# The scale applies a new mode on its next loop pass and then has to reach
# the new server before it reports backendOk.
SWITCH_CONFIRM_TIMEOUT_S = 45
POLL_INTERVAL_S = 2


class ScaleError(Exception):
    """A request to the scale failed. code is what the page translates:
    scale_unreachable, scale_password, scale_refused, scale_bad_answer."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class ScaleClient:
    def __init__(self, address: str, password: str = ""):
        self.address = address
        self.password = password

    def _request(self, method: str, path: str, body: bytes | None = None) -> bytes:
        req = urllib.request.Request(f"http://{self.address}{path}", data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "text/plain")
        if self.password:
            token = base64.b64encode(f"spoolmanscale-pro:{self.password}".encode()).decode()
            req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ScaleError("scale_password") from e
            # 403: the share is switched off on the scale, or it does not
            # take this address as its own name.
            raise ScaleError("scale_refused", f"HTTP {e.code} on {path}") from e
        except (urllib.error.URLError, OSError) as e:
            raise ScaleError("scale_unreachable", str(e)) from e

    def status(self) -> dict:
        raw = self._request("GET", "/status.json")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ScaleError("scale_bad_answer", "status.json is not JSON") from e
        if not isinstance(data, dict) or "backend" not in data:
            raise ScaleError("scale_bad_answer", "status.json has no backend field")
        return data

    def set_mode(self, mode: int) -> None:
        self._request("POST", "/api/backend/mode", str(mode).encode())


def own_address_towards(host: str) -> str | None:
    """The address this Pi has on the network that leads to host. A UDP
    connect sends nothing, it only picks the route."""
    name = host.split(":")[0]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((name, 80))
            return s.getsockname()[0]
    except OSError:
        return None


def own_names(scale_address: str) -> set[str]:
    """The names under which the scale could know this Pi."""
    host = socket.gethostname()
    names = {host, f"{host}.local"}
    address = own_address_towards(scale_address)
    if address:
        names.add(address)
    return names


def summarize(status: dict, backend: Backend | None, own_names: set[str]) -> dict:
    """What the page shows about the scale, from its status.json. Pure.

    points_here: the scale's address for its current backend is this Pi.
    Without it the scale may be on the right backend but talking to a
    different server.
    """
    url = str(status.get("backendUrl", ""))
    host = urllib.parse.urlsplit(url if "//" in url else f"http://{url}").hostname or ""
    return {
        "reachable": True,
        "version": status.get("version", ""),
        "backend": status.get("backend", ""),
        "backend_url": url,
        "backend_ok": bool(status.get("backendOk")),
        "on_active": backend is not None and status.get("backend") == backend.scale_name,
        "points_here": host.lower() in {n.lower() for n in own_names},
        "weight": status.get("weight", ""),
    }


def switch_and_confirm(client: ScaleClient, backend: Backend,
                       timeout_s: int = SWITCH_CONFIRM_TIMEOUT_S,
                       sleep=time.sleep, clock=time.monotonic) -> dict:
    """Switches the scale to backend and waits until it reports that backend
    as reached. Returns the last status; raises ScaleError when the scale
    could not be told."""
    status = client.status()
    if status.get("backend") != backend.scale_name:
        client.set_mode(backend.scale_mode)
    deadline = clock() + timeout_s
    while True:
        status = client.status()
        if status.get("backend") == backend.scale_name and status.get("backendOk"):
            return status
        if clock() >= deadline:
            log.warning("Scale did not confirm %s within %d s (reports %s, ok=%s)",
                        backend.key, timeout_s, status.get("backend"), status.get("backendOk"))
            return status
        sleep(POLL_INTERVAL_S)
