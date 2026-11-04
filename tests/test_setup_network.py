"""The helper's way back from the setup WLAN and the hotspot. Only a real Pi
can prove the radio, so this runs the shell verbs against a stand-in nmcli that
keeps its state in files, to prove the decisions."""

import os
import stat
import subprocess
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / "system" / "host-helper.sh"
SETUP = "spoolmanscale-setup"
HOTSPOT = "spoolmanscale-hotspot"

NMCLI = r"""#!/bin/sh
echo "$*" >> "$STATE/log"
case "$*" in
  "-t -f TYPE,STATE,CONNECTION device") cat "$STATE/devices" ;;
  "-t -f TYPE,STATE device") sed 's/:[^:]*$//' "$STATE/devices" ;;
  "-t -f NAME connection show --active") cat "$STATE/active" ;;
  "-g NAME,TYPE connection show") cat "$STATE/profiles" ;;
  *"connection up id "*)
    args="$*"; name="${args##*connection up id }"
    if [ "$name" = spoolmanscale-setup ] || [ "$name" = spoolmanscale-hotspot ]; then
      echo "$name" > "$STATE/active"
    elif grep -Fxq "$name" "$STATE/reachable"; then
      echo "$name" > "$STATE/active"; echo "wifi:connected:$name" > "$STATE/devices"
    else
      exit 10
    fi ;;
  *"connection down id "*) : > "$STATE/active" ;;
esac
"""
# Moves the world on at the N-th sleep, and ends a run that would go on forever.
SLEEP = r"""#!/bin/sh
n=$(($(cat "$STATE/sleeps") + 1)); echo "$n" > "$STATE/sleeps"
[ -f "$STATE/router_back_at" ] && [ "$n" -ge "$(cat "$STATE/router_back_at")" ] && echo Home > "$STATE/reachable"
[ "$n" -ge 40 ] && exit 99
exit 0
"""


def run(tmp_path, verb, **world):
    devices = world.get("devices", "wifi:disconnected:\n")
    profiles = world.get("profiles", f"Home:802-11-wireless\n{SETUP}:802-11-wireless\n")
    back_at = world.get("back_at")
    neigh = world.get("neigh", "")
    state = tmp_path / "state"
    state.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("devices", devices), ("active", world.get("active", "")), ("profiles", profiles),
                       ("reachable", world.get("reachable", "")), ("sleeps", "0"), ("log", "")):
        (state / name).write_text(text)
    if back_at:
        (state / "router_back_at").write_text(str(back_at))
    for name, text in (("nmcli", NMCLI), ("sleep", SLEEP), ("ip", f"#!/bin/sh\nprintf '%s' '{neigh}'\n")):
        tool = bin_dir / name
        tool.write_text(text)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "STATE": str(state)}
    done = subprocess.run(["sh", str(HELPER), verb], env=env, capture_output=True, text=True, timeout=30)
    return done, (state / "active").read_text().strip(), (state / "log").read_text()


def test_router_back_after_a_power_cut_ends_the_setup_wlan(tmp_path):
    # 18 sleeps of 5 s are the 90 s at boot; the router is back two rounds on.
    done, active, _ = run(tmp_path, "setup-ap-if-offline", back_at=20)
    assert done.returncode == 0 and active == "Home"


def test_setup_wlan_comes_back_while_nothing_is_in_reach(tmp_path):
    done, active, log = run(tmp_path, "setup-ap-if-offline")
    assert done.returncode == 99  # the stand-in sleep ended the endless wait
    assert active == SETUP
    assert log.count(f"connection down id {SETUP}") > 1


def test_setup_wlan_stays_for_a_connected_phone(tmp_path):
    done, active, log = run(tmp_path, "setup-ap-if-offline", reachable="Home\n", neigh="192.168.50.20 lladdr aa STALE")
    assert done.returncode == 99 and active == SETUP
    assert f"connection down id {SETUP}" not in log


def test_setup_wlan_stays_with_nothing_saved(tmp_path):
    done, active, log = run(tmp_path, "setup-ap-if-offline", profiles=f"{SETUP}:802-11-wireless\n")
    assert done.returncode == 99 and active == SETUP
    assert f"connection down id {SETUP}" not in log


def test_online_at_boot_opens_nothing(tmp_path):
    done, _, log = run(tmp_path, "setup-ap-if-offline", devices="wifi:connected:Home\n", active="Home\n")
    assert done.returncode == 0
    assert "connection add" not in log


def test_hotspot_off_joins_a_wlan_in_reach(tmp_path):
    done, active, _ = run(tmp_path, "hotspot-off", devices=f"wifi:connected:{HOTSPOT}\n", active=f"{HOTSPOT}\n",
                          profiles=f"Home:802-11-wireless\n{HOTSPOT}:802-11-wireless\n", reachable="Home\n")
    assert done.returncode == 0 and active == "Home"


def test_hotspot_stays_when_the_saved_wlan_is_out_of_reach(tmp_path):
    done, active, log = run(tmp_path, "hotspot-off", devices=f"wifi:connected:{HOTSPOT}\n", active=f"{HOTSPOT}\n",
                            profiles=f"Home:802-11-wireless\n{HOTSPOT}:802-11-wireless\n")
    assert done.returncode == 6 and active == HOTSPOT
    assert f"connection modify {HOTSPOT} connection.autoconnect yes" in log


def test_hotspot_off_refused_with_nothing_saved(tmp_path):
    done, active, _ = run(tmp_path, "hotspot-off", devices=f"wifi:connected:{HOTSPOT}\n", active=f"{HOTSPOT}\n",
                          profiles=f"{HOTSPOT}:802-11-wireless\n")
    assert done.returncode == 4 and active == HOTSPOT
