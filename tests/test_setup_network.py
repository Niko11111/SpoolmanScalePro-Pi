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
  "-g NAME,TYPE connection show") cut -d: -f1,2 "$STATE/profiles" ;;
  "-t -f TIMESTAMP,TYPE,NAME connection show") awk -F: '{ print ($3 == "" ? 0 : $3) ":" $2 ":" $1 }' "$STATE/profiles" ;;
  "-t -f NAME,DEVICE connection show --active") sed -n 's/$/:wlan0/p' "$STATE/active" ;;
  *"connection delete id "*) ;;
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


def run(tmp_path, verb, *args, **world):
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
    done = subprocess.run(["sh", str(HELPER), verb, *args], env=env, capture_output=True, text=True, timeout=30)
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


# Saved WLANs: NAME:TYPE:TIMESTAMP, the one used last has the largest stamp.
SAVED = f"Home:802-11-wireless:200\nWork:802-11-wireless:100\n{HOTSPOT}:802-11-wireless:300\n"
ON_HOME = {"devices": "wifi:connected:Home\n", "active": "Home\n", "profiles": SAVED}


def test_wifi_up_joins_a_saved_wlan(tmp_path):
    done, active, _ = run(tmp_path, "wifi-up", "Work", reachable="Home\nWork\n", **ON_HOME)
    assert done.returncode == 0 and active == "Work"


def test_wifi_up_goes_back_when_the_saved_wlan_fails(tmp_path):
    done, active, log = run(tmp_path, "wifi-up", "Work", reachable="Home\n", **ON_HOME)
    assert done.returncode == 3 and active == "Home"
    assert log.rstrip().endswith("connection up id Home")


def test_wifi_up_takes_only_a_saved_client_wlan(tmp_path):
    for name in ("Cafe", HOTSPOT, ""):
        world = tmp_path / (name or "empty")
        world.mkdir()
        done, _, log = run(world, "wifi-up", name, reachable="Home\n", **ON_HOME)
        assert done.returncode == 2 and "connection up" not in log, name


def test_wifi_forget_deletes_a_saved_wlan(tmp_path):
    done, _, log = run(tmp_path, "wifi-forget", "Work", **ON_HOME)
    assert done.returncode == 0 and "connection delete id Work" in log


def test_wifi_forget_refuses_the_wlan_in_use(tmp_path):
    done, _, log = run(tmp_path, "wifi-forget", "Home", **ON_HOME)
    assert done.returncode == 7 and "connection delete" not in log


def test_hotspot_off_tries_the_wlan_used_last_first(tmp_path):
    done, active, _ = run(tmp_path, "hotspot-off", devices=f"wifi:connected:{HOTSPOT}\n", active=f"{HOTSPOT}\n",
                          profiles="Old:802-11-wireless:100\nNew:802-11-wireless:200\n", reachable="Old\nNew\n")
    assert done.returncode == 0 and active == "New"
