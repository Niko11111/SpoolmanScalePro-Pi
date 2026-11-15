"""network.py where it decides before nmcli or the helper is asked: which
name it hands nmcli, and that the WLAN in use is never forgotten."""

from spoolmanscale_pro import network
from spoolmanscale_pro.host_actions import HelperResult


def test_ssid_lookup_names_the_connection_with_id_and_takes_one_line(monkeypatch):
    calls = []

    def read(cmd):
        calls.append(cmd)
        return "Home@H\nHome@H\n"
    monkeypatch.setattr(network, "_read", read)
    assert network._ssid_of("--active") == "Home@H"
    assert calls[0][-2:] == ["id", "--active"]


def test_the_wlan_in_use_is_not_forgotten_even_if_the_page_offers_it(monkeypatch):
    helper = []
    monkeypatch.setattr(network, "status", lambda: {"wlan": {"mode": "client", "connection": "Hotel: Guest"}})
    monkeypatch.setattr(network, "run_helper", lambda *args, **kw: helper.append(args) or HelperResult(0, ""))
    assert network.forget("Hotel: Guest") == "wifi_in_use"
    assert helper == []
    assert network.forget("Work") is None
    assert helper == [("wifi-forget", "Work")]


def test_hotspot_password_is_what_the_helper_prints_without_its_line_end(monkeypatch):
    monkeypatch.setattr(network, "run_helper", lambda *args, **kw: HelperResult(0, "k7mp-x2qd-9rta\n"))
    assert network.hotspot_password() == "k7mp-x2qd-9rta"
    monkeypatch.setattr(network, "run_helper", lambda *args, **kw: HelperResult(2, ""))
    assert network.hotspot_password() == ""
