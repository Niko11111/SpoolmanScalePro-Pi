from spoolmanscale_pro import os_update_rules as r

SIMULATION = """Reading package lists...
Building dependency tree...
Calculating upgrade...
The following packages will be upgraded:
  libssl3 linux-image-rpi-v8 openssl
Inst libssl3 [3.0.15-1~deb12u1] (3.0.17-1~deb12u2 Debian-Security:12/stable-security [arm64])
Inst linux-image-rpi-v8 [1:6.6.51-1+rpt3] (1:6.12.25-1+rpt1 Raspberry Pi Foundation:stable [arm64])
Inst newpkg (1.0-1 Debian:12/stable [arm64])
Remv oldpkg [0.9-1]
Conf libssl3 (3.0.17-1~deb12u2 Debian-Security:12/stable-security [arm64])
2 upgraded, 1 newly installed, 1 to remove and 0 not upgraded.
"""


def test_packages_removals_and_summary():
    result = r.build_result(SIMULATION)
    assert [p["name"] for p in result["packages"]] == ["libssl3", "linux-image-rpi-v8", "newpkg"]
    assert result["packages"][0] == {"name": "libssl3", "current": "3.0.15-1~deb12u1",
                                     "candidate": "3.0.17-1~deb12u2"}
    assert result["packages"][2]["current"] is None
    assert result["removals"] == ["oldpkg"]
    assert result["summary"] == {"upgraded": 2, "newly_installed": 1, "removed": 1}
    assert result["mismatch"] is False
    assert result["restart_after"] is True


def test_nothing_to_do():
    result = r.build_result("Reading package lists...\n0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n")
    assert result["packages"] == [] and result["mismatch"] is False and result["restart_after"] is False


def test_mismatch_when_a_line_format_was_missed():
    text = "Inst only-one [1] (2 x)\n2 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n"
    assert r.build_result(text)["mismatch"] is True


def test_exit_code_from_the_log():
    assert r.exit_code("Setting up openssl ...\n") is None
    assert r.exit_code("done\nSSPRO-EXIT:0\n") == 0
    assert r.exit_code("SSPRO-EXIT:100\n") == 100


def test_kernel_restart():
    running = "6.6.51+rpt-rpi-v8"
    assert not r.kernel_restart_needed(running, [])
    assert not r.kernel_restart_needed(running, [running, "6.6.51+rpt-rpi-2712"])
    # A Pi 5 kernel with a "bigger" number is another flavour, not newer.
    assert not r.kernel_restart_needed(running, [running, "6.12.25+rpt-rpi-2712"])
    assert r.kernel_restart_needed(running, [running, "6.12.25+rpt-rpi-v8"])
    assert r.kernel_restart_needed(running, ["6.12.25+rpt-rpi-v8"])
