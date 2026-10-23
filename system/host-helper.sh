#!/bin/sh
# The only thing the SpoolmanScale Pro service may run as root.
#
# Installed root-owned to /usr/local/libexec/spoolmanscale-pro/host-helper;
# system/sudoers lets the service user run exactly this file. Every verb is
# listed below and checks its own argument. Anything else is refused.
set -eu

die() { echo "host-helper: $*" >&2; exit 2; }

verb="${1:-}"
case "$verb" in
  reboot)
    # Detached, so the caller gets its answer before the system goes.
    systemd-run --on-active=2 --timer-property=AccuracySec=100ms /bin/systemctl reboot
    ;;
  poweroff)
    systemd-run --on-active=2 --timer-property=AccuracySec=100ms /bin/systemctl poweroff
    ;;
  set-time)
    epoch="${2:-}"
    case "$epoch" in
      ''|*[!0-9]*) die "set-time needs epoch seconds" ;;
    esac
    # 2024-01-01 .. 2100-01-01, as in host_actions.py.
    [ "$epoch" -ge 1704067200 ] && [ "$epoch" -le 4102444800 ] || die "set-time out of range"
    date -u -s "@$epoch" >/dev/null
    # Keep it across a reboot without network: fake-hwclock restores the
    # last saved time at boot instead of 1970. "force", because without it
    # fake-hwclock never saves a time earlier than the one it has, and a
    # clock that ran ahead must be correctable.
    if command -v fake-hwclock >/dev/null 2>&1; then
      fake-hwclock save force
    fi
    ;;
  *)
    die "unknown verb '$verb'"
    ;;
esac
