from spoolmanscale_pro import network_rules as nr

SCAN = (
    " :Home:54:WPA2:6\n"
    "*:Home:81:WPA2:11\n"
    " :Cafe\\: Free:40::1\n"
    " ::70:WPA2:6\n"
    " :Back\\\\slash:30:WPA1 WPA2:11\n"
)


def test_split_terse_resolves_escapes():
    assert nr.split_terse("a\\:b:c\\\\d:") == ["a:b", "c\\d", ""]


def test_wifi_list_keeps_the_strongest_per_name_and_drops_hidden():
    rows = nr.parse_wifi_list(SCAN)
    assert [r["ssid"] for r in rows] == ["Home", "Cafe: Free", "Back\\slash"]
    home = rows[0]
    assert home["signal"] == 81 and home["in_use"] and home["channel"] == 11
    assert rows[1]["secure"] is False and rows[2]["secure"] is True


def test_in_use_survives_when_a_weaker_ap_is_the_used_one():
    rows = nr.parse_wifi_list(" :Net:90:WPA2:1\n*:Net:20:WPA2:6\n")
    assert rows == [{"ssid": "Net", "signal": 90, "secure": True, "channel": 1, "in_use": True}]


def test_active_connections():
    text = "Home:802-11-wireless:wlan0\nWired connection 1:802-3-ethernet:eth0\nlo:loopback:lo\n"
    rows = nr.parse_active(text)
    assert rows[0] == {"name": "Home", "type": "802-11-wireless", "device": "wlan0"}
    assert len(rows) == 3


def test_hostnames():
    assert nr.valid_hostname("spoolmanscale-pro")
    assert nr.valid_hostname("demo")
    for bad in ("spoolmanscale_pro", "-pi", "pi-", "Pi", "a" * 64, "", "pi.local", None):
        assert not nr.valid_hostname(bad), bad


def test_ssid_and_psk():
    assert nr.valid_ssid("Home WLAN")
    assert not nr.valid_ssid("x" * 33)
    assert not nr.valid_ssid("a\nb")
    assert nr.valid_psk("", allow_empty=True)
    assert not nr.valid_psk("", allow_empty=False)
    assert not nr.valid_psk("short", allow_empty=True)
    assert nr.valid_psk("eight888", allow_empty=False)
    assert not nr.valid_psk("x" * 64, allow_empty=False)


def test_channels():
    assert nr.valid_channel(6)
    assert not nr.valid_channel(5) and not nr.valid_channel(True) and not nr.valid_channel("6")


def test_ip_addresses():
    text = ("2: eth0    inet 192.168.4.20/24 brd 192.168.4.255 scope global dynamic eth0\\       valid_lft\n"
            "3: wlan0    inet 192.168.50.1/24 brd 192.168.50.255 scope global wlan0\n")
    assert nr.parse_ip_addresses(text) == {"eth0": "192.168.4.20", "wlan0": "192.168.50.1"}


def test_wlan_mode():
    hot, setup = "spoolmanscale-hotspot", "spoolmanscale-setup"
    assert nr.wlan_mode([], hot, setup)["mode"] == "off"
    assert nr.wlan_mode([{"name": hot, "type": "x", "device": "wlan0"}], hot, setup)["mode"] == "hotspot"
    assert nr.wlan_mode([{"name": setup, "type": "x", "device": "wlan0"}], hot, setup)["mode"] == "setup"
    home = nr.wlan_mode([{"name": "Home", "type": "x", "device": "wlan0"},
                         {"name": "Wired", "type": "y", "device": "eth0"}], hot, setup)
    assert home == {"mode": "client", "connection": "Home"}


def test_primary_address_prefers_the_cable_and_never_shows_docker():
    both = {"docker0": "172.17.0.1", "wlan0": "192.168.4.31", "eth0": "192.168.4.30"}
    assert nr.primary_address(both) == "192.168.4.30"
    assert nr.primary_address({"br-1a2b": "172.18.0.1", "wlan0": "192.168.50.1"}) == "192.168.50.1"
    assert nr.primary_address({"end0": "10.0.0.5"}) == "10.0.0.5"
    assert nr.primary_address({"docker0": "172.17.0.1"}) is None
    assert nr.primary_address({}) is None


def test_hostnames_the_network_or_the_scale_needs():
    assert nr.reserved_hostname("localhost") and not nr.reserved_hostname("demo")
    assert nr.hostname_of_the_scale("spoolmanscale")
    assert not nr.hostname_of_the_scale("spoolmanscale-pro")


SAVED = (
    "1794615075:802-11-wireless:spoolmanscale-hotspot\n"
    "1794615127:802-3-ethernet:netplan-eth0\n"
    "1794535515:802-11-wireless:netplan-wlan0-Home@H\n"
    "1794700000:802-11-wireless:Werkstatt\\: 2,4\n"
    "0:802-11-wireless:spoolmanscale-setup\n"
    "0:802-11-wireless:Never used\n"
)
OWN = ("spoolmanscale-hotspot", "spoolmanscale-setup")


def test_parse_saved_lists_client_wlans_used_last_first():
    assert nr.parse_saved(SAVED, OWN) == ["Werkstatt: 2,4", "netplan-wlan0-Home@H", "Never used"]


def test_parse_saved_without_any_wlan():
    assert nr.parse_saved("1:802-3-ethernet:netplan-eth0\n", OWN) == []


def test_mark_saved_names_the_connection_used_last_per_ssid():
    networks = [{"ssid": "Home@H"}, {"ssid": "Cafe"}]
    saved = [{"name": "netplan-wlan0-Home@H", "ssid": "Home@H"}, {"name": "Home@H 1", "ssid": "Home@H"}]
    marked = nr.mark_saved(networks, saved)
    assert marked == [{"ssid": "Home@H", "saved_name": "netplan-wlan0-Home@H"}, {"ssid": "Cafe", "saved_name": None}]


def test_valid_connection_name():
    assert nr.valid_connection_name("netplan-wlan0-Home@H")
    assert nr.valid_connection_name("Werkstatt: 2,4")
    for bad in ("", None, 5, "a\nb", "a\rb", "a\0b", "x" * 256):
        assert not nr.valid_connection_name(bad), bad


def test_own_access_point_is_left_out_of_the_scan_while_it_runs():
    networks = [{"ssid": "SpoolmanScale-Pro", "in_use": True}, {"ssid": "Home", "in_use": False}]
    assert nr.without_own_access_point(networks, True) == [{"ssid": "Home", "in_use": False}]
    assert nr.without_own_access_point(networks, False) == networks


def test_suggested_psk_is_a_valid_password_in_three_groups_of_four():
    import re
    for _ in range(50):
        psk = nr.suggested_psk()
        assert re.fullmatch(r"[a-hj-km-np-z2-9]{4}-[a-hj-km-np-z2-9]{4}-[a-hj-km-np-z2-9]{4}", psk), psk
        assert nr.valid_psk(psk, allow_empty=False)
    assert len({nr.suggested_psk() for _ in range(20)}) == 20
