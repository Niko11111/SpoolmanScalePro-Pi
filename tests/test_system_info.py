from spoolmanscale_pro.system_info import (parse_meminfo, parse_millidegrees, parse_throttled, power_seen,
                                           parse_uptime)

MEMINFO = """MemTotal:         921616 kB
MemFree:          120000 kB
MemAvailable:     409600 kB
SwapTotal:        460800 kB
SwapFree:         358400 kB
"""


def test_meminfo_uses_available_not_free():
    m = parse_meminfo(MEMINFO)
    assert m["ram_total_mib"] == 900
    assert m["ram_used_mib"] == 900 - 400
    assert m["swap_total_mib"] == 450 and m["swap_used_mib"] == 100


def test_meminfo_without_the_needed_lines():
    assert parse_meminfo("MemTotal: 1 kB\n") is None


def test_temperature_and_uptime():
    assert parse_millidegrees("48312\n") == 48.3
    assert parse_millidegrees("n/a") is None
    assert parse_uptime("3725.42 9000.1\n") == 3725
    assert parse_uptime("") is None


def test_throttled_bits():
    assert parse_throttled("throttled=0x0") == {"now": [], "since_boot": []}
    # Under-voltage now and since boot, and throttled now: a weak power supply.
    assert parse_throttled("throttled=0x50005") == {
        "now": ["under_voltage", "throttled"], "since_boot": ["under_voltage", "throttled"]}
    assert parse_throttled("throttled=0x10000") == {"now": [], "since_boot": ["under_voltage"]}
    assert parse_throttled("garbage") is None


def test_power_seen_holds_for_one_boot():
    assert power_seen("b1", "b1") is True
    assert power_seen("b1", "b2") is False
    assert power_seen("", "b1") is False
    assert power_seen("", None) is False
