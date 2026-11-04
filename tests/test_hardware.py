from spoolmanscale_pro import hardware as hw

ZERO_2W, PI_3, PI_4_2GB = 427, 906, 1845 + 100

MEMINFO_PI3 = "MemTotal:         927924 kB\nMemFree:  1 kB\n"


def test_sizes_and_rules():
    assert hw.rules(ZERO_2W) == {"size": "small", "parallel": "blocked", "memory_limits": True,
                                 "parallel_default": False, "slow_backends": ["filaman", "bambuddy"]}
    assert hw.rules(PI_3)["parallel"] == "warn" and hw.rules(PI_3)["slow_backends"] == []
    big = hw.rules(4096)
    assert big["parallel"] == "free" and big["parallel_default"] and not big["memory_limits"]


def test_budget_on_a_pi_3():
    two_small = hw.budget(PI_3, ["spoolman"], "bambuddy")
    assert two_small == {"after_mb": 271 + 180 + 420, "total_mb": PI_3, "fits": True}
    with_filaman = hw.budget(PI_3, ["spoolman", "bambuddy"], "filaman")
    assert not with_filaman["fits"]


def test_one_filaman_worker_makes_room_on_a_pi_3():
    four = hw.budget(PI_3, ["bambuddy"], "filaman")
    one = hw.budget(PI_3, ["bambuddy"], "filaman", 1)
    assert four == {"after_mb": 271 + 480 + 420, "total_mb": PI_3, "fits": False}
    assert one == {"after_mb": 271 + 201 + 420, "total_mb": PI_3, "fits": True}


def test_filaman_workers():
    assert hw.filaman_workers(ZERO_2W) == 1
    assert hw.filaman_workers(858, "Raspberry Pi 3 Model B Rev 1.2") == 1
    assert hw.filaman_workers(3800, "Raspberry Pi 4 Model B Rev 1.4") == 4
    # The owner's choice wins, also against the automatic one on a big Pi.
    assert hw.filaman_workers(ZERO_2W, "", 3) == 3
    assert hw.filaman_workers(3800, "Raspberry Pi 4 Model B Rev 1.4", 2) == 2


def test_memory_limits():
    # At most what the Pi has to spare, but never below a backend's typical
    # use: the Zero has 156 MB to spare, less than any of them needs.
    assert hw.memory_limits(ZERO_2W, "", 1) == {"spoolman": 180, "filaman": 201, "bambuddy": 420}
    assert hw.memory_limits(PI_3) == {"spoolman": 360, "filaman": 635, "bambuddy": 635}
    assert hw.memory_limits(PI_3, "", 1) == {"spoolman": 360, "filaman": 402, "bambuddy": 635}
    assert hw.memory_limits(4096) == {}


def test_meminfo_and_laptop():
    assert hw.parse_meminfo_total(MEMINFO_PI3) == 906
    laptop = {"model": "", "ram_mb": 16000, "is_pi": False}
    assert hw.rules(hw.effective_ram_mb(laptop))["parallel"] == "free"


def test_the_model_wins_over_the_reported_ram():
    assert hw.size_of(858, "Raspberry Pi 3 Model B Rev 1.2") == "medium"
    assert hw.size_of(427, "Raspberry Pi Zero 2 W Rev 1.0") == "small"
    assert hw.size_of(3800, "Raspberry Pi 4 Model B Rev 1.4") == "large"
    assert hw.size_of(858) == "small"
