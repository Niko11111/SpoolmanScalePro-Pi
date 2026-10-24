#!/usr/bin/env bash
# The one check before anything counts as done, locally and in CI:
# the house rules (check_conventions.py) and the tests.
#
# Needs the development environment once:
#   python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# and node for the JavaScript syntax check.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python3
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
fi

status=0
echo "== conventions"
"$PY" scripts/check_conventions.py "$@" || status=1
echo "== tests"
"$PY" -m pytest -q || status=1

if [ "$status" -ne 0 ]; then
  echo "check: FAILED"
else
  echo "check: passed"
fi
exit "$status"
