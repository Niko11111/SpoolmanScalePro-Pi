#!/usr/bin/env bash
# Installs or updates SpoolmanScale Pro on a Raspberry Pi (64-bit Raspberry
# Pi OS Lite, Bookworm or Trixie). Run from a checkout of this repository:
#
#   sudo scripts/install.sh              install, or update to this checkout
#   sudo scripts/install.sh --pull-all   also download all three backends now,
#                                        so they can start later without internet
#
# Safe to run again. Each version goes to /opt/spoolmanscale-pro/releases/
# <version>, and /opt/spoolmanscale-pro/current points at the active one; the
# previous release stays on disk until the next update replaces it.
# The data under /var/lib/spoolmanscale-pro and the backends' Docker volumes
# are never touched.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$SRC/VERSION")"
SERVICE_USER=spoolmanscale
BASE=/opt/spoolmanscale-pro
RELEASE="$BASE/releases/$VERSION"
DATA=/var/lib/spoolmanscale-pro
HELPER_DIR=/usr/local/libexec/spoolmanscale-pro
# Releases kept on disk: the active one and the one before it.
KEEP_RELEASES=2

PULL_ALL=0
for arg in "$@"; do
  case "$arg" in
    --pull-all) PULL_ALL=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }
die() { echo "install: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run with sudo"
[ "$(uname -m)" = "aarch64" ] || echo "warning: $(uname -m) is not the tested aarch64"

install_packages() {
  say "System packages"
  apt-get update -qq
  # avahi: the Pi answers as <hostname>.local. fake-hwclock: the clock comes
  # back from the last shutdown instead of 1970 when there is no network.
  # network-manager: the WLAN page and the hotspot speak nmcli (the default
  # since Raspberry Pi OS Bookworm).
  apt-get install -y -qq python3-venv avahi-daemon fake-hwclock curl network-manager >/dev/null
  if ! command -v docker >/dev/null 2>&1; then
    say "Docker (Docker's own installer, as its documentation advises for Raspberry Pi OS)"
    curl -fsSL https://get.docker.com | sh
  fi
  docker compose version >/dev/null 2>&1 || die "docker compose is missing"
}

setup_swap() {
  # Compressed swap in RAM: a backend that briefly needs more than 1 GB is
  # slowed down instead of killed. Recent Raspberry Pi OS already has it.
  if [ -e /sys/block/zram0 ]; then
    return
  fi
  say "Compressed swap (zram)"
  apt-get install -y -qq zram-tools >/dev/null
  printf 'ALGO=zstd\nPERCENT=50\nPRIORITY=100\n' > /etc/default/zramswap
  systemctl restart zramswap
}

create_user() {
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    say "Service user $SERVICE_USER"
    useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin "$SERVICE_USER"
  fi
  # The docker group is as powerful as root. The service needs it to start
  # and stop the backends; the page's password is what protects it.
  usermod -aG docker "$SERVICE_USER"
  install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA"
}

install_release() {
  say "Release $VERSION"
  rm -rf "$RELEASE"
  install -d "$RELEASE"
  for part in VERSION LICENSE requirements.txt spoolmanscale_pro compose templates static system; do
    cp -R "$SRC/$part" "$RELEASE/"
  done
  python3 -m venv "$RELEASE/.venv"
  "$RELEASE/.venv/bin/pip" install --quiet --no-cache-dir -r "$RELEASE/requirements.txt"
  chown -R root:root "$RELEASE"
  ln -sfn "$RELEASE" "$BASE/current.new"
  mv -T "$BASE/current.new" "$BASE/current"
  # Newest first; everything after the first KEEP_RELEASES goes.
  ls -1dt "$BASE"/releases/* | tail -n +$((KEEP_RELEASES + 1)) | xargs -r rm -rf
}

# Raspberry Pi Imager's default name is replaced by the product's, so the
# Pi answers as spoolmanscale-pro.local. A name chosen in the Imager stays.
# Not spoolmanscale.local: that name belongs to the scale.
DEFAULT_HOSTNAME=spoolmanscale-pro
IMAGER_DEFAULT_HOSTNAME=raspberrypi

set_default_hostname() {
  if [ "$(hostname)" = "$IMAGER_DEFAULT_HOSTNAME" ]; then
    say "Host name $DEFAULT_HOSTNAME"
    "$HELPER_DIR/host-helper" set-hostname "$DEFAULT_HOSTNAME"
  fi
}

install_system_files() {
  say "Helper, sudoers rule, services"
  install -d "$HELPER_DIR"
  install -m 0755 -o root -g root "$SRC/system/host-helper.sh" "$HELPER_DIR/host-helper"
  install -m 0440 -o root -g root "$SRC/system/sudoers" /etc/sudoers.d/spoolmanscale-pro.new
  visudo -cf /etc/sudoers.d/spoolmanscale-pro.new >/dev/null || die "sudoers rule rejected by visudo"
  mv /etc/sudoers.d/spoolmanscale-pro.new /etc/sudoers.d/spoolmanscale-pro
  install -m 0644 "$SRC/system/spoolmanscale-pro.service" /etc/systemd/system/spoolmanscale-pro.service
  install -m 0644 "$SRC/system/spoolmanscale-pro-setup-ap.service" \
    /etc/systemd/system/spoolmanscale-pro-setup-ap.service
  systemctl daemon-reload
  # Runs at the next boot; not now, the Pi is online while this installs.
  systemctl enable --quiet spoolmanscale-pro-setup-ap
  systemctl enable --quiet spoolmanscale-pro
  systemctl restart spoolmanscale-pro
}

pull_backends() {
  say "Downloading all backends (for offline use)"
  docker compose --project-name spoolmanscale-pro --file "$BASE/current/compose/docker-compose.yml" \
    --profile spoolman --profile filaman --profile bambuddy pull
}

install_packages
setup_swap
create_user
install_release
install_system_files
set_default_hostname
if [ "$PULL_ALL" -eq 1 ]; then
  pull_backends
fi

say "Done: SpoolmanScale Pro $VERSION"
echo "Open http://$(hostname).local or http://$(hostname -I | awk '{print $1}')"
