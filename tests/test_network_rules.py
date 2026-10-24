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
