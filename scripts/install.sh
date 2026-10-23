#!/usr/bin/env bash
# Installs or updates SpoolmanScale Pro on a Raspberry Pi (64-bit Raspberry
# Pi OS Lite, Bookworm or Trixie). Run from a checkout or a release archive:
#
#   sudo scripts/install.sh              install, or update to this version
#   sudo scripts/install.sh --pull-all   also download all three backends now,
#                                        so they can start later without internet
#
# Safe to run again. Each version goes to /opt/spoolmanscale-pro/releases/
# <version>, and /opt/spoolmanscale-pro/current points at the active one; the
# one before stays, to go back to. The data under /var/lib/spoolmanscale-pro
# and the backends' Docker volumes are never touched.
#
# Everything it prints also goes to LOG. When a step fails, the last lines
# say which one, and the log has the rest.
set -Eeuo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$SRC/VERSION")"
SERVICE_USER=spoolmanscale
BASE=/opt/spoolmanscale-pro
RELEASE="$BASE/releases/$VERSION"
DATA=/var/lib/spoolmanscale-pro
HELPER_DIR=/usr/local/libexec/spoolmanscale-pro
LOG_DIR=/var/log/spoolmanscale-pro
LOG="$LOG_DIR/install.log"
# Releases kept on disk: the active one and the one before it.
KEEP_RELEASES=2
# What one backend at a time needs (FilaMan, the largest, about 370 MB), plus
# the system. Below this the Pi is too small, not just slow.
MIN_RAM_MB=900
# All three images (about 3 GB) and room for backups.
MIN_DISK_MB_PULL_ALL=4500
MIN_DISK_MB=1500
# Raspberry Pi Imager's default name is replaced by the product's, so the Pi
# answers as spoolmanscale-pro.local. A name chosen in the Imager stays. Not
# spoolmanscale: that name belongs to the scale.
DEFAULT_HOSTNAME=spoolmanscale-pro
IMAGER_DEFAULT_HOSTNAME=raspberrypi
STEPS=9

PULL_ALL=0
for arg in "$@"; do
  case "$arg" in
    --pull-all) PULL_ALL=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step=0
current_step="preparing"
step() {
  step=$((step + 1))
  current_step="$*"
  printf '\n[%d/%d] %s\n' "$step" "$STEPS" "$*"
}
note() { printf '      %s\n' "$*"; }
die() { printf '\ninstall: %s\n' "$*" >&2; exit 1; }
on_error() {
  printf '\ninstall: failed at step %d (%s).\nThe full log: %s\n' "$step" "$current_step" "$LOG" >&2
}

[ "$(id -u)" -eq 0 ] || die "run with sudo: sudo scripts/install.sh"
install -d -m 0755 "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
trap on_error ERR
printf '\n===== SpoolmanScale Pro %s, %s =====\n' "$VERSION" "$(date -Is)"

preflight() {
  step "Checking this Pi"
  [ "$(uname -m)" = "aarch64" ] || die "needs 64-bit Raspberry Pi OS (this is $(uname -m))"
  # In a subshell: os-release sets VERSION, which would replace ours.
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
  case "$codename" in
    bookworm|trixie) note "Raspberry Pi OS $codename" ;;
    *) note "warning: '$codename' is not tested; Bookworm and Trixie are" ;;
  esac
  ram_mb=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)
  [ "$ram_mb" -ge "$MIN_RAM_MB" ] || die "needs about 1 GB of RAM (this Pi has $ram_mb MB)"
  free_mb=$(df -Pm / | awk 'NR == 2 {print $4}')
  need_mb=$MIN_DISK_MB
  [ "$PULL_ALL" -eq 1 ] && need_mb=$MIN_DISK_MB_PULL_ALL
  [ "$free_mb" -ge "$need_mb" ] || die "needs $need_mb MB free on the SD card ($free_mb MB are)"
  curl -fsS --max-time 10 -o /dev/null https://ghcr.io/ \
    || die "no internet: the install downloads packages and Docker images"
  note "RAM $ram_mb MB, SD card $free_mb MB free, internet reachable"
}

install_packages() {
  step "System packages"
  apt-get -o DPkg::Lock::Timeout=300 update -qq
  # avahi: the Pi answers as <hostname>.local; avahi-utils finds scales.
  # fake-hwclock: the clock comes back from the last shutdown, not 1970.
  # network-manager: the Network page and the hotspot speak nmcli.
  # unattended-upgrades: Debian's security fixes, every day.
  apt-get -o DPkg::Lock::Timeout=300 install -y -qq python3-venv avahi-daemon avahi-utils \
    fake-hwclock curl network-manager unattended-upgrades >/dev/null
  if ! command -v docker >/dev/null 2>&1; then
    note "Docker (Docker's own installer, as its documentation advises for Raspberry Pi OS)"
    curl -fsSL https://get.docker.com | sh
  fi
  docker compose version >/dev/null 2>&1 || die "docker compose is missing"
  note "$(docker --version)"
}

harden_system() {
  step "Watchdog, logs, security updates, SSH"
  install -d /etc/systemd/system.conf.d /etc/systemd/journald.conf.d /etc/ssh/sshd_config.d
  install -m 0644 "$SRC/system/watchdog.conf" /etc/systemd/system.conf.d/spoolmanscale-pro-watchdog.conf
  install -m 0644 "$SRC/system/journald.conf" /etc/systemd/journald.conf.d/spoolmanscale-pro.conf
  install -m 0644 "$SRC/system/auto-upgrades.conf" /etc/apt/apt.conf.d/20auto-upgrades
  systemctl daemon-reexec
  systemctl restart systemd-journald
  # Compressed swap in RAM: a backend that briefly needs more than 1 GB is
  # slowed down instead of killed. Recent Raspberry Pi OS has it already.
  if [ ! -e /sys/block/zram0 ]; then
    apt-get -o DPkg::Lock::Timeout=300 install -y -qq zram-tools >/dev/null
    printf 'ALGO=zstd\nPERCENT=50\nPRIORITY=100\n' > /etc/default/zramswap
    systemctl restart zramswap
  fi
  harden_ssh
}

harden_ssh() {
  # No root login over SSH. Passwords off only once a key is there: without
  # one, switching them off would lock out whoever set the Pi up.
  conf=/etc/ssh/sshd_config.d/50-spoolmanscale-pro.conf
  printf '# Written by SpoolmanScale Pro scripts/install.sh\nPermitRootLogin no\n' > "$conf"
  if find /home -maxdepth 3 -path '*/.ssh/authorized_keys' -size +0 2>/dev/null | grep -q .; then
    printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' >> "$conf"
    note "SSH: keys only, no root login"
  else
    note "SSH: no root login. Passwords still allowed: no SSH key on this Pi yet."
    note "      Add one (ssh-copy-id) and run this installer again to switch passwords off."
  fi
  # A configuration sshd refuses would lock everyone out at its next start.
  if sshd -t; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
  else
    rm -f "$conf"
    note "SSH: sshd refused the change, left as it was"
  fi
}

create_user() {
  step "Service user"
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin "$SERVICE_USER"
  fi
  # docker: start and stop the backends (as powerful as root; the page's
  # login is what protects it). video: vcgencmd, for the power supply check.
  usermod -aG docker,video "$SERVICE_USER"
  install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA"
}

install_release() {
  step "SpoolmanScale Pro $VERSION"
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

install_system_files() {
  step "Root helper, sudoers rule, services"
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

set_default_hostname() {
  step "Name on the network"
  if [ "$(hostname)" = "$IMAGER_DEFAULT_HOSTNAME" ]; then
    "$HELPER_DIR/host-helper" set-hostname "$DEFAULT_HOSTNAME"
    note "renamed to $DEFAULT_HOSTNAME"
  else
    note "keeps its name $(hostname)"
  fi
}

pull_backends() {
  step "Backends"
  if [ "$PULL_ALL" -ne 1 ]; then
    note "downloaded when first started (add --pull-all to have them for offline use)"
    return
  fi
  note "downloading Spoolman, FilaMan and BamBuddy, about 3 GB"
  docker compose --project-name spoolmanscale-pro --file "$BASE/current/compose/docker-compose.yml" \
    --profile spoolman --profile filaman --profile bambuddy pull
}

check_running() {
  step "Checking the service"
  for _ in $(seq 1 20); do
    if curl -fsS --max-time 2 -o /dev/null http://127.0.0.1/api/auth/state; then
      note "answering"
      return
    fi
    sleep 1
  done
  die "the service does not answer; see: journalctl -u spoolmanscale-pro -n 50"
}

preflight
install_packages
harden_system
create_user
install_release
install_system_files
set_default_hostname
pull_backends
check_running

name="$(hostname)"
address="$(hostname -I | awk '{print $1}')"
printf '\nSpoolmanScale Pro %s is installed.\n\n' "$VERSION"
printf '  Open   http://%s.local   or   http://%s\n' "$name" "$address"
printf '  Then   create the login, pick a backend, pair the scale.\n'
printf '  Log    %s\n\n' "$LOG"
