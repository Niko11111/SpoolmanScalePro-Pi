"""system/ap-psk-only.py: which WLANs it touches and what it tells
wpa_supplicant. The file is a dispatcher hook, not part of the package, so it
is loaded by its path."""

import importlib.util
import socket
import tempfile
import threading
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "system" / "ap-psk-only.py"
_spec = importlib.util.spec_from_file_location("ap_psk_only", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

AP_STATUS = "bssid=b8:27:eb:c0:3e:3f\nfreq=2437\nssid=SpoolmanScale-Pro\nid=0\nmode=AP\nkey_mgmt=UNKNOWN\nwpa_state=COMPLETED\n"


class FakeControl:
    def __init__(self, status: str, key_mgmt: str):
        self.replies = {"STATUS": status, "GET_NETWORK 0 key_mgmt": key_mgmt}
        self.sent: list[str] = []

    def ask(self, command: str) -> str:
        self.sent.append(command)
        return self.replies.get(command, "OK")

    def do(self, command: str) -> None:
        self.ask(command)


def no_sleep(monkeypatch):
    monkeypatch.setattr(hook.time, "sleep", lambda s: None)


def test_only_the_pis_own_wlans_when_they_come_up():
    assert hook.applies_to("up", "spoolmanscale-hotspot")
    assert hook.applies_to("up", "spoolmanscale-setup")
    assert not hook.applies_to("down", "spoolmanscale-hotspot")
    assert not hook.applies_to("up", "netplan-wlan0-Home")
    assert not hook.applies_to("up", "")


def test_parse_status_reads_key_value_lines():
    status = hook.parse_status(AP_STATUS)
    assert status["id"] == "0" and status["mode"] == "AP"


def test_narrows_an_access_point_that_offers_sha256(monkeypatch):
    no_sleep(monkeypatch)
    control = FakeControl(AP_STATUS, "WPA-PSK WPA-PSK-SHA256")
    hook.narrow(control, "spoolmanscale-hotspot")
    assert control.sent[2:] == ["SET_NETWORK 0 key_mgmt WPA-PSK", "DISABLE_NETWORK 0", "ENABLE_NETWORK 0"]


def test_leaves_an_access_point_alone_that_is_already_narrowed(monkeypatch):
    no_sleep(monkeypatch)
    control = FakeControl(AP_STATUS, "WPA-PSK")
    hook.narrow(control, "spoolmanscale-hotspot")
    assert control.sent == ["STATUS", "GET_NETWORK 0 key_mgmt"]


def test_leaves_a_client_wlan_alone(monkeypatch):
    no_sleep(monkeypatch)
    control = FakeControl(AP_STATUS.replace("mode=AP", "mode=station"), "WPA-PSK WPA-PSK-SHA256")
    hook.narrow(control, "spoolmanscale-hotspot")
    assert control.sent == ["STATUS"]


def test_main_ignores_other_connections_without_touching_the_socket():
    assert hook.main(["hook", "wlan0", "up"], {"CONNECTION_ID": "netplan-wlan0-Home"}) == 0
    assert hook.main(["hook"], {}) == 0



def short_dir() -> Path:
    """A directory of its own under /tmp: macOS keeps AF_UNIX paths short."""
    return Path(tempfile.mkdtemp(prefix="ap", dir="/tmp"))


def test_control_talks_over_a_reply_socket_in_its_own_directory_and_cleans_up(monkeypatch):
    base = short_dir()
    control_dir, runtime_dir = base / "c", base / "r"
    control_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(hook, "CONTROL_DIR", str(control_dir))
    monkeypatch.setattr(hook, "RUNTIME_DIR", str(runtime_dir))
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(str(control_dir / "wlan0"))

    def answer():
        data, peer = server.recvfrom(64)
        server.sendto(b"PONG " + data, peer)
    threading.Thread(target=answer, daemon=True).start()
    control = hook.Control("wlan0")
    try:
        assert control.ask("PING") == "PONG PING"
        assert Path(control.own_path).parent.parent == runtime_dir
    finally:
        control.close()
        server.close()
    assert list(runtime_dir.iterdir()) == []


def test_control_cleans_up_when_wpa_supplicant_is_missing(monkeypatch):
    base = short_dir()
    monkeypatch.setattr(hook, "CONTROL_DIR", str(base / "missing"))
    monkeypatch.setattr(hook, "RUNTIME_DIR", str(base))
    with pytest.raises(OSError):
        hook.Control("wlan0")
    assert list(base.iterdir()) == []
