#!/usr/bin/python3
"""NetworkManager dispatcher hook: the Pi's own WLANs offer WPA-PSK only.

Installed by scripts/install.sh to /etc/NetworkManager/dispatcher.d/ and run
by NetworkManager as root, with the interface and the action as arguments
and the connection's name in CONNECTION_ID.

Why: NetworkManager 1.52 offers WPA-PSK-SHA256 next to WPA-PSK in every
access point it starts, and no connection setting leaves it out (pmf disable
does not). The Pi 3's radio (brcmfmac) cannot carry both as an access point:
a phone sees the WLAN, its password checks out in step 2 of the handshake,
and it still leaves after step 3 and reports a wrong password (measured with
an iPhone, 13.11.2026). Narrowed to WPA-PSK in the running wpa_supplicant,
the same phone joins. The access point restarts for that, so the WLAN is
gone for a moment each time it comes up.
"""

import os
import socket
import sys
import syslog
import tempfile
import time

OWN_CONNECTIONS = ("spoolmanscale-hotspot", "spoolmanscale-setup")
WANTED_KEY_MGMT = "WPA-PSK"
CONTROL_DIR = "/run/wpa_supplicant"
REPLY_TIMEOUT_S = 5
RESTART_PAUSE_S = 1
REPLY_MAX_BYTES = 8192


class ControlError(Exception):
    """wpa_supplicant refused a command."""


def applies_to(action: str, connection: str) -> bool:
    """Only when one of the Pi's own WLANs has just come up."""
    return action == "up" and connection in OWN_CONNECTIONS


def parse_status(text: str) -> dict[str, str]:
    """wpa_supplicant's STATUS reply, one key=value per line."""
    pairs = (line.split("=", 1) for line in text.splitlines() if "=" in line)
    return {key: value for key, value in pairs}


class Control:
    """wpa_supplicant's control socket for one interface (what wpa_cli does,
    which Raspberry Pi OS Lite does not ship)."""

    def __init__(self, interface: str):
        self.own_path = os.path.join(tempfile.gettempdir(), f"sspro-wpactl-{os.getpid()}")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.settimeout(REPLY_TIMEOUT_S)
        self.sock.bind(self.own_path)
        try:
            self.sock.connect(os.path.join(CONTROL_DIR, interface))
        except OSError:
            self.close()
            raise

    def ask(self, command: str) -> str:
        self.sock.send(command.encode())
        return self.sock.recv(REPLY_MAX_BYTES).decode().strip()

    def do(self, command: str) -> None:
        reply = self.ask(command)
        if reply != "OK":
            raise ControlError(f"{command.split()[0]} answered {reply!r}")

    def close(self) -> None:
        self.sock.close()
        os.unlink(self.own_path)


def narrow(control: Control, connection: str) -> None:
    status = parse_status(control.ask("STATUS"))
    network = status.get("id")
    if status.get("mode") != "AP" or network is None:
        syslog.syslog(syslog.LOG_WARNING, f"{connection}: wlan0 is not an access point, left as it is")
        return
    if control.ask(f"GET_NETWORK {network} key_mgmt") == WANTED_KEY_MGMT:
        return
    control.do(f"SET_NETWORK {network} key_mgmt {WANTED_KEY_MGMT}")
    control.do(f"DISABLE_NETWORK {network}")
    time.sleep(RESTART_PAUSE_S)
    control.do(f"ENABLE_NETWORK {network}")
    syslog.syslog(f"{connection}: access point restarted with {WANTED_KEY_MGMT} only")


def main(argv: list[str], env: dict[str, str]) -> int:
    if len(argv) < 3 or not applies_to(argv[2], env.get("CONNECTION_ID", "")):
        return 0
    connection = env["CONNECTION_ID"]
    syslog.openlog("spoolmanscale-pro-ap")
    try:
        control = Control(argv[1])
    except OSError as e:
        syslog.syslog(syslog.LOG_ERR, f"{connection}: no wpa_supplicant control socket ({e}); phones may refuse the password")
        return 1
    try:
        narrow(control, connection)
    except (OSError, ControlError) as e:
        syslog.syslog(syslog.LOG_ERR, f"{connection}: narrowing to {WANTED_KEY_MGMT} failed ({e}); phones may refuse the password")
        return 1
    finally:
        control.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv, dict(os.environ)))
