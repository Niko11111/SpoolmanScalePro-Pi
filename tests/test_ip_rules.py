from spoolmanscale_pro.ip_rules import check_static, parse_device_show, with_prefix

SHOW = """GENERAL.HWADDR:B8\\:27\\:EB\\:12\\:34\\:56
IP4.ADDRESS[1]:192.168.4.20/24
IP4.GATEWAY:192.168.4.1
IP4.DNS[1]:192.168.4.1
IP4.DNS[2]:9.9.9.9
"""


def test_parse_device_show():
    assert parse_device_show(SHOW) == {"address": "192.168.4.20/24", "gateway": "192.168.4.1",
                                       "dns": ["192.168.4.1", "9.9.9.9"], "mac": "B8:27:EB:12:34:56"}
    assert parse_device_show("")["address"] == ""


def test_check_static():
    current, gateway = "192.168.4.20/24", "192.168.4.1"
    assert check_static("192.168.4.50", current, gateway) is None
    assert check_static("192.168.5.50", current, gateway) == "ip_other_network"
    assert check_static("192.168.4.0", current, gateway) == "ip_reserved"
    assert check_static("192.168.4.255", current, gateway) == "ip_reserved"
    assert check_static("192.168.4.1", current, gateway) == "ip_is_gateway"
    assert check_static("192.168.4.300", current, gateway) == "ip_invalid"
    assert check_static("x; reboot", current, gateway) == "ip_invalid"
    assert check_static("8.8.8.8", "8.8.8.1/24", "8.8.8.254") == "ip_not_private"


def test_with_prefix():
    assert with_prefix("192.168.4.50", "192.168.4.20/24") == "192.168.4.50/24"
