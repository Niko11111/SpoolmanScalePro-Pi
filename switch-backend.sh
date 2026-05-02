#!/bin/bash
# SpoolmanScale Pro - Backend Switcher
# Usage: ./switch-backend.sh [spoolman|filaman|off|status|auto]

set -e
cd "$(dirname "$0")"

MARKER=".active-backend"

stop_all() {
  /usr/bin/docker compose -f compose-spoolman.yml down 2>/dev/null || true
  /usr/bin/docker compose -f compose-filaman.yml down 2>/dev/null || true
}

case "$1" in
  spoolman)
    echo "Switching to Spoolman..."
    stop_all
    mkdir -p spoolman-data
    chown -R 1000:1001 spoolman-data
    chmod -R 775 spoolman-data
    /usr/bin/docker compose -f compose-spoolman.yml up -d
    echo "spoolman" > "$MARKER"
    echo "Spoolman is now active on http://$(hostname -I | awk '{print $1}'):7912"
    ;;
  filaman)
    echo "Switching to FilaMan..."
    stop_all
    mkdir -p filaman-data
    chown -R 1000:1000 filaman-data
    chmod -R 775 filaman-data
    /usr/bin/docker compose -f compose-filaman.yml up -d
    echo "filaman" > "$MARKER"
    echo "FilaMan is now active on http://$(hostname -I | awk '{print $1}'):8002"
    ;;
  off)
    echo "Stopping all backends..."
    stop_all
    rm -f "$MARKER"
    echo "All backends stopped."
    ;;
  status)
    if [ -f "$MARKER" ]; then
      echo "Active backend: $(cat $MARKER)"
    else
      echo "Active backend: none"
    fi
    echo ""
    echo "Running containers:"
    /usr/bin/docker ps --filter "name=spoolman" --filter "name=filaman" \
      --format "  {{.Names}}  {{.Status}}  {{.Ports}}" 2>/dev/null || true
    ;;
  auto)
    # Called by systemd at boot - restart last active backend
    if [ -f "$MARKER" ]; then
      "$0" "$(cat $MARKER)"
    else
      echo "No backend configured, nothing to start."
    fi
    ;;
  *)
    echo "Usage: $0 {spoolman|filaman|off|status|auto}"
    exit 1
    ;;
esac
