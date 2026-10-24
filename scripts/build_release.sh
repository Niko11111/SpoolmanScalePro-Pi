#!/usr/bin/env bash
# Builds the release archive of the committed state, as the release workflow
# does and the Pi's self-update downloads:
#   dist/spoolmanscale-pro-<VERSION>.tar.gz   (files at the archive's root)
#   dist/spoolmanscale-pro-<VERSION>.tar.gz.sha256
#   dist/release-notes.md                     (this version's CHANGELOG section)
# What goes in: everything Git tracks, minus export-ignore in .gitattributes.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(cat VERSION)"
NAME="spoolmanscale-pro-$VERSION.tar.gz"
mkdir -p dist

git archive --worktree-attributes --format=tar.gz --output="dist/$NAME" HEAD
(cd dist && sha256sum "$NAME" > "$NAME.sha256" 2>/dev/null || shasum -a 256 "$NAME" > "$NAME.sha256")

# The section "## <VERSION>" of CHANGELOG.md, up to the next "## ".
awk -v head="## $VERSION" '
  $0 == head { found = 1; next }
  found && /^## / { exit }
  found { print }
' CHANGELOG.md > dist/release-notes.md
[ -s dist/release-notes.md ] || { echo "build_release: CHANGELOG.md has no section for $VERSION" >&2; exit 1; }

echo "Built dist/$NAME"
