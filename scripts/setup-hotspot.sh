#!/usr/bin/env bash
# Turns the Pi's WLAN into an access point of its own, for running without
# any other network (a fair stand, a workshop). The scale and a tablet join
# it; the Pi hands out addresses and is always at HOTSPOT_ADDRESS.
#
#   sudo scripts/setup-hotspot.sh --ssid SpoolmanScale-Demo [--channel 6]
#   sudo scripts/setup-hotspot.sh --remove
#
# The WLAN password is asked for on the terminal rather than taken as an
# option, so it stays out of the shell history. NetworkManager stores it;
# it is never written into this repository.
# While the hotspot is on, wlan0 cannot also be a client: internet for the
# Pi then only comes over the Ethernet port.
#
# Needs NetworkManager, the default since Raspberry Pi OS Bookworm.
set -euo pipefail

CONNECTION=spoolmanscale-hotspot
HOTSPOT_ADDRESS=192.168.50.1
PREFIX_LEN=24
# 2.4 GHz only: the scale's ESP32 has no 5 GHz radio. 1, 6 and 11 are the
# channels that do not overlap each other.
ALLOWED_CHANNELS="1 6 11"
PSK_MIN_LEN=8

die() { echo "setup-hotspot: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run with sudo"
command -v nmcli >/dev/null 2>&1 || die "NetworkManager (nmcli) is not installed"

SSID=""
CHANNEL=6
while [ $# -gt 0 ]; do
  case "$1" in
    --ssid) SSID="${2:-}"; shift 2 ;;
    --channel) CHANNEL="${2:-}"; shift 2 ;;
    --remove)
      nmcli connection delete "$CONNECTION" >/dev/null 2>&1 || true
      echo "Hotspot removed. wlan0 connects to known networks again."
      exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -n "$SSID" ] || die "--ssid is required"
case " $ALLOWED_CHANNELS " in
  *" $CHANNEL "*) ;;
  *) die "--channel must be one of: $ALLOWED_CHANNELS" ;;
esac

read -r -s -p "WLAN password for $SSID (at least $PSK_MIN_LEN characters): " PSK
echo
[ "${#PSK}" -ge "$PSK_MIN_LEN" ] || die "password too short"

nmcli connection delete "$CONNECTION" >/dev/null 2>&1 || true
# ipv4.method shared: NetworkManager runs DHCP for the clients itself.
nmcli connection add type wifi ifname wlan0 con-name "$CONNECTION" \
  autoconnect yes connection.autoconnect-priority 100 \
  ssid "$SSID" mode ap 802-11-wireless.band bg 802-11-wireless.channel "$CHANNEL" \
  ipv4.method shared ipv4.addresses "$HOTSPOT_ADDRESS/$PREFIX_LEN" ipv6.method disabled \
  wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp \
  wifi-sec.psk "$PSK" >/dev/null
# Without this the WLAN chip saves power by dropping frames, which shows as
# a scale that loses the connection now and then.
nmcli connection modify "$CONNECTION" 802-11-wireless.powersave 2
nmcli connection up "$CONNECTION" >/dev/null

echo "Hotspot '$SSID' on channel $CHANNEL. The Pi is at $HOTSPOT_ADDRESS and $(hostname).local."
