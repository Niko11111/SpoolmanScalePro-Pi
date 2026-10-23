#!/bin/sh
# The only thing the SpoolmanScale Pro service may run as root.
#
# Installed root-owned to /usr/local/libexec/spoolmanscale-pro/host-helper;
# system/sudoers lets the service user run exactly this file. Every verb is
# listed in the case at the bottom and checks its own input. Anything else is
# refused. Secrets (WLAN passwords) come on stdin, never as arguments.
#
# Verbs:
#   reboot | poweroff
#   set-time EPOCH_SECONDS
#   set-hostname NAME
#   wifi-scan                      prints nmcli -t rows
#   wifi-connect     (stdin: SSID, PSK)            join a WLAN, fall back if it fails
#   hotspot-on       (stdin: SSID, PSK, CHANNEL)   the Pi's own WLAN
#   hotspot-off                                     back to the known WLANs
#   setup-ap-if-offline            at boot: open the setup WLAN if nothing connected
#   apt-check                      refresh the package lists, print a simulated upgrade
#   os-upgrade-start               run the upgrade as its own systemd unit, log in UPGRADE_LOG
#   self-update VERSION            install that release of SpoolmanScale Pro from GitHub
#   self-rollback                  go back to the release installed before
set -eu

HOTSPOT_CONNECTION=spoolmanscale-hotspot
SETUP_CONNECTION=spoolmanscale-setup
# The setup WLAN is only up while the Pi has no other network. Its password
# is printed in the README: it keeps strangers from joining by accident, not
# by intent, and the page behind it still asks for a login of its own.
SETUP_SSID=SpoolmanScale-Pro-Setup
SETUP_PSK=spoolmanscale
HOTSPOT_ADDRESS=192.168.50.1/24
CONNECT_WAIT_S=45
OFFLINE_WAIT_S=90
OFFLINE_POLL_S=5

# The upgrade runs as a unit of its own, not as a child of the service: if
# the service restarts meanwhile (apt may update Python), dpkg is not cut
# off halfway. The service follows it through the log (os_update.py).
UPGRADE_UNIT=spoolmanscale-pro-os-upgrade
UPGRADE_LOG_DIR=/var/log/spoolmanscale-pro
UPGRADE_LOG=$UPGRADE_LOG_DIR/os-upgrade.log

# Self-update: the release archives the release workflow publishes. The
# repository is fixed here; only the version comes from the caller.
RELEASE_BASE=https://github.com/Niko11111/SpoolmanScalePro-Pi/releases/download
SELF_UPDATE_UNIT=spoolmanscale-pro-self-update
SELF_UPDATE_LOG=$UPGRADE_LOG_DIR/self-update.log
INSTALL_BASE=/opt/spoolmanscale-pro

die() { echo "host-helper: $*" >&2; exit 2; }

# Detached, so the caller gets its answer before the system goes.
later() { systemd-run --on-active=2 --timer-property=AccuracySec=100ms "$@" >/dev/null; }

set_time() {
  epoch="${1:-}"
  case "$epoch" in ''|*[!0-9]*) die "set-time needs epoch seconds" ;; esac
  # 2024-01-01 .. 2100-01-01, as in host_actions.py.
  [ "$epoch" -ge 1704067200 ] && [ "$epoch" -le 4102444800 ] || die "set-time out of range"
  date -u -s "@$epoch" >/dev/null
  # Keep it across a reboot without network. "force", because otherwise
  # fake-hwclock never saves a time earlier than the one it has.
  if command -v fake-hwclock >/dev/null 2>&1; then
    fake-hwclock save force
  fi
}

set_hostname() {
  name="${1:-}"
  # The same rule as network_rules.HOSTNAME_RE.
  echo "$name" | grep -Eqx '[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?' || die "invalid host name"
  hostnamectl set-hostname "$name"
  if grep -q '^127\.0\.1\.1' /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$name/" /etc/hosts
  else
    printf '127.0.1.1\t%s\n' "$name" >> /etc/hosts
  fi
  # avahi announces the new <name>.local right away.
  systemctl restart avahi-daemon
}

wifi_scan() {
  nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY,CHAN device wifi list --rescan yes ifname wlan0
}

active_wifi() {
  nmcli -t -f NAME,DEVICE connection show --active | sed -n 's/^\(.*\):wlan0$/\1/p' | head -n 1
}

wifi_connect() {
  IFS= read -r ssid || die "wifi-connect needs the network name on stdin"
  IFS= read -r psk || psk=""
  [ -n "$ssid" ] || die "empty network name"
  previous="$(active_wifi)"
  existed=0
  nmcli -g NAME connection show | grep -Fxq -- "$ssid" && existed=1
  # The password reaches nmcli as an argument: visible to root in the
  # process list for the second it runs, which on this single-user Pi is
  # the same trust as the file NetworkManager keeps it in.
  if [ -n "$psk" ]; then
    ok=0; nmcli --wait "$CONNECT_WAIT_S" device wifi connect "$ssid" password "$psk" ifname wlan0 >/dev/null && ok=1
  else
    ok=0; nmcli --wait "$CONNECT_WAIT_S" device wifi connect "$ssid" ifname wlan0 >/dev/null && ok=1
  fi
  if [ "$ok" = 1 ]; then
    # A client WLAN now; the Pi's own hotspot must not take wlan0 back at boot.
    nmcli connection modify "$HOTSPOT_CONNECTION" connection.autoconnect no 2>/dev/null || true
    return 0
  fi
  # Failed: leave no half profile behind, and go back where the Pi was.
  [ "$existed" = 1 ] || nmcli connection delete id "$ssid" >/dev/null 2>&1 || true
  if [ -n "$previous" ]; then
    nmcli --wait 30 connection up id "$previous" >/dev/null 2>&1 || true
  fi
  exit 3
}

make_ap() {
  # $1 connection, $2 ssid, $3 psk, $4 channel, $5 autoconnect yes|no
  nmcli connection delete id "$1" >/dev/null 2>&1 || true
  # ipv4.method shared: NetworkManager runs DHCP for the clients itself.
  nmcli connection add type wifi ifname wlan0 con-name "$1" \
    autoconnect "$5" connection.autoconnect-priority 100 \
    ssid "$2" mode ap 802-11-wireless.band bg 802-11-wireless.channel "$4" \
    802-11-wireless.powersave 2 \
    ipv4.method shared ipv4.addresses "$HOTSPOT_ADDRESS" ipv6.method disabled \
    wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp \
    wifi-sec.psk "$3" >/dev/null
}

hotspot_on() {
  IFS= read -r ssid || die "hotspot-on needs a network name"
  IFS= read -r psk || die "hotspot-on needs a password"
  IFS= read -r channel || die "hotspot-on needs a channel"
  [ -n "$ssid" ] || die "empty network name"
  [ "${#psk}" -ge 8 ] && [ "${#psk}" -le 63 ] || die "password must have 8 to 63 characters"
  case "$channel" in 1|6|11) ;; *) die "channel must be 1, 6 or 11" ;; esac
  make_ap "$HOTSPOT_CONNECTION" "$ssid" "$psk" "$channel" yes
  # The setup WLAN is not needed while the Pi has its own.
  nmcli connection down id "$SETUP_CONNECTION" >/dev/null 2>&1 || true
  nmcli --wait 30 connection up id "$HOTSPOT_CONNECTION" >/dev/null
}

has_other_network() {
  # A cable with a link, or a saved client WLAN to go back to.
  nmcli -t -f TYPE,STATE device | grep -q '^ethernet:connected$' && return 0
  nmcli -g NAME,TYPE connection show | grep ':802-11-wireless$' \
    | grep -v -e "^$HOTSPOT_CONNECTION:" -e "^$SETUP_CONNECTION:" | grep -q .
}

hotspot_off() {
  has_other_network || { echo "host-helper: no other network to fall back to" >&2; exit 4; }
  nmcli connection modify "$HOTSPOT_CONNECTION" connection.autoconnect no 2>/dev/null || true
  nmcli connection down id "$HOTSPOT_CONNECTION" >/dev/null 2>&1 || true
  # NetworkManager now joins the best known WLAN by itself.
}

is_online() {
  nmcli -t -f TYPE,STATE,CONNECTION device | grep -E '^(ethernet|wifi):connected:' \
    | grep -vq -e ":$SETUP_CONNECTION\$" -e ":$HOTSPOT_CONNECTION\$"
}

hotspot_active() {
  nmcli -t -f NAME connection show --active | grep -Fxq "$HOTSPOT_CONNECTION"
}

setup_ap_if_offline() {
  waited=0
  while [ "$waited" -lt "$OFFLINE_WAIT_S" ]; do
    # Our own hotspot counts as a network: nothing to rescue. Checked in the
    # loop, because at boot it can take a few seconds to come up.
    is_online && return 0
    hotspot_active && return 0
    sleep "$OFFLINE_POLL_S"
    waited=$((waited + OFFLINE_POLL_S))
  done
  echo "host-helper: no network after ${OFFLINE_WAIT_S} s, opening $SETUP_SSID"
  make_ap "$SETUP_CONNECTION" "$SETUP_SSID" "$SETUP_PSK" 6 no
  nmcli --wait 30 connection up id "$SETUP_CONNECTION" >/dev/null
}

apt_check() {
  # English output whatever the Pi's language: os_update_rules.py parses it.
  export LC_ALL=C DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get -s full-upgrade
}

os_upgrade_start() {
  if systemctl is-active --quiet "$UPGRADE_UNIT"; then
    echo "host-helper: an upgrade is already running" >&2
    exit 5
  fi
  systemctl reset-failed "$UPGRADE_UNIT" >/dev/null 2>&1 || true
  install -d -m 0755 "$UPGRADE_LOG_DIR"
  : > "$UPGRADE_LOG"
  chmod 0644 "$UPGRADE_LOG"
  # dpkg --configure -a first: after an upgrade cut off by a power loss apt
  # refuses everything until it ran; with nothing pending it does nothing.
  # confdef/confold: a configuration file changed by hand is kept, and the
  # upgrade never stops to ask. The last line carries the exit code.
  systemd-run --unit="$UPGRADE_UNIT" --description="SpoolmanScale Pro: Raspberry Pi OS upgrade" \
    --setenv=LC_ALL=C --setenv=DEBIAN_FRONTEND=noninteractive \
    /bin/sh -c '{ dpkg --configure -a && apt-get update && apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold full-upgrade; } >> "$0" 2>&1; echo "SSPRO-EXIT:$?" >> "$0"' "$UPGRADE_LOG" >/dev/null
}

self_update() {
  version="${1:-}"
  # The same form as VERSION; check_conventions.py checks VERSION for it.
  echo "$version" | grep -Eqx '[0-9]+\.[0-9]+\.[0-9]+(-beta\.[0-9]+)?' || die "invalid version"
  if systemctl is-active --quiet "$SELF_UPDATE_UNIT"; then
    echo "host-helper: an update is already running" >&2
    exit 5
  fi
  systemctl reset-failed "$SELF_UPDATE_UNIT" >/dev/null 2>&1 || true
  install -d -m 0755 "$UPGRADE_LOG_DIR"
  : > "$SELF_UPDATE_LOG"
  chmod 0644 "$SELF_UPDATE_LOG"
  # A unit of its own: the release's install.sh restarts the service, which
  # would end anything the service started itself. The checksum guards
  # against a broken download, not against a forged release.
  systemd-run --unit="$SELF_UPDATE_UNIT" --description="SpoolmanScale Pro: update to $version" \
    /bin/sh -c '
      v="$1"; log="$2"; base="$3"
      exec >>"$log" 2>&1
      trap "echo SSPRO-EXIT:\$?" EXIT
      set -e
      tmp="$(mktemp -d)"
      name="spoolmanscale-pro-$v.tar.gz"
      curl -fsSL -o "$tmp/$name" "$base/v$v/$name"
      curl -fsSL -o "$tmp/$name.sha256" "$base/v$v/$name.sha256"
      (cd "$tmp" && sha256sum -c "$name.sha256")
      mkdir "$tmp/src"
      tar -xzf "$tmp/$name" -C "$tmp/src"
      "$tmp/src/scripts/install.sh"
      rm -rf "$tmp"
    ' sh "$version" "$SELF_UPDATE_LOG" "$RELEASE_BASE" >/dev/null
}

self_rollback() {
  current="$(readlink -f "$INSTALL_BASE/current")"
  previous="$(ls -1dt "$INSTALL_BASE"/releases/* | grep -vxF "$current" | head -n 1)"
  [ -n "$previous" ] || die "no earlier release on this Pi"
  ln -sfn "$previous" "$INSTALL_BASE/current.new"
  mv -T "$INSTALL_BASE/current.new" "$INSTALL_BASE/current"
  # Touched, so the release just left counts as the older one from now on.
  touch "$previous"
  later /bin/systemctl restart spoolmanscale-pro
}

verb="${1:-}"
case "$verb" in
  reboot)              later /bin/systemctl reboot ;;
  poweroff)            later /bin/systemctl poweroff ;;
  set-time)            set_time "${2:-}" ;;
  set-hostname)        set_hostname "${2:-}" ;;
  wifi-scan)           wifi_scan ;;
  wifi-connect)        wifi_connect ;;
  hotspot-on)          hotspot_on ;;
  hotspot-off)         hotspot_off ;;
  setup-ap-if-offline) setup_ap_if_offline ;;
  apt-check)           apt_check ;;
  os-upgrade-start)    os_upgrade_start ;;
  self-update)         self_update "${2:-}" ;;
  self-rollback)       self_rollback ;;
  *)                   die "unknown verb '$verb'" ;;
esac
