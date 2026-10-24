from spoolmanscale_pro.scale_discovery import parse_avahi

AVAHI = """+;wlan0;IPv4;SpoolmanScale;Web Site;local
=;wlan0;IPv6;SpoolmanScale;Web Site;local;spoolmanscale.local;fe80::1;80;"backend=Spoolman" "model=WT32-SC01-Plus" "id=ssc-a84674b535d8" "fw=v0.8.3-beta.87"
=;wlan0;IPv4;SpoolmanScale;Web Site;local;spoolmanscale.local;192.168.4.37;80;"backend=Spoolman" "model=WT32-SC01-Plus" "id=ssc-a84674b535d8" "fw=v0.8.3-beta.87"
=;wlan0;IPv4;Werkstatt\\032Waage;Web Site;local;werkstatt.local;192.168.4.41;80;"model=WT32-SC01-Plus" "id=ssc-2" "fw=v0.8.2" "backend=FilaMan"
=;wlan0;IPv4;Canon MG7700 series;Web Site;local;canon.local;192.168.4.20;80;"txtvers=1"
=;wlan0;IPv4;Panda_Breath_X1C;Web Site;local;panda.local;192.168.4.30;80;
"""


def test_only_scales_one_entry_each_ipv4_preferred():
    scales = parse_avahi(AVAHI)
    assert [s["name"] for s in scales] == ["SpoolmanScale", "Werkstatt Waage"]
    first = scales[0]
    assert first == {"name": "SpoolmanScale", "host": "spoolmanscale.local", "address": "192.168.4.37",
                     "port": 80, "id": "ssc-a84674b535d8", "firmware": "v0.8.3-beta.87", "backend": "Spoolman"}
    assert scales[1]["backend"] == "FilaMan"


def test_nothing_found():
    assert parse_avahi("") == []
