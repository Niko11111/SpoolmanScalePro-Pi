#!/usr/bin/env bash
# From a development machine to a Pi, without pushing anything:
#   scripts/deploy-to-pi.sh pi@192.168.4.50 [--pull-all]
# Copies the files Git knows (committed or not, never .venv or .devdata) to
# ~/spoolmanscale-pro-src on the Pi and runs the installer there, which asks
# for the Pi user's sudo password if it needs one.
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"
[ -n "$TARGET" ] || { echo "usage: scripts/deploy-to-pi.sh user@host [--pull-all]" >&2; exit 2; }
shift
REMOTE_DIR=spoolmanscale-pro-src

# A fresh copy each time: a file renamed here must not linger there, where
# the installer would copy it into the release.
ssh "$TARGET" "rm -rf ~/$REMOTE_DIR && mkdir ~/$REMOTE_DIR"
git ls-files --cached --others --exclude-standard -z \
  | rsync -a --from0 --files-from=- ./ "$TARGET:$REMOTE_DIR/"
ssh -t "$TARGET" "cd $REMOTE_DIR && sudo scripts/install.sh $*"
