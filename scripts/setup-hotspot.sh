#!/usr/bin/env bash
# The Pi's own WLAN from the command line, for a Pi without a browser at
# hand. The page does the same under Network. Needs scripts/install.sh first:
# the work is done by the installed helper (verbs hotspot-on, hotspot-off).
#
#   sudo scripts/setup-hotspot.sh --ssid SpoolmanScale-Demo [--channel 6]
#   sudo scripts/setup-hotspot.sh --remove
#
# The WLAN password is asked for on the terminal rather than taken as an
# option, so it stays out of the shell history.
set -euo pipefail

HELPER=/usr/local/libexec/spoolmanscale-pro/host-helper

die() { echo "setup-hotspot: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run with sudo"
[ -x "$HELPER" ] || die "run scripts/install.sh first"

SSID=""
CHANNEL=6
while [ $# -gt 0 ]; do
  case "$1" in
    --ssid) SSID="${2:-}"; shift 2 ;;
    --channel) CHANNEL="${2:-}"; shift 2 ;;
    --remove) "$HELPER" hotspot-off && echo "Hotspot off. wlan0 joins known networks again."; exit ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -n "$SSID" ] || die "--ssid is required"

read -r -s -p "WLAN password for $SSID (8 to 63 characters): " PSK
echo
printf '%s\n%s\n%s\n' "$SSID" "$PSK" "$CHANNEL" | "$HELPER" hotspot-on
echo "Hotspot '$SSID' on channel $CHANNEL. The Pi is at 192.168.50.1 and $(hostname).local."
