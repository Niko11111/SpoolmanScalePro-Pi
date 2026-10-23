"""Telling versions apart in image tags and release names. Pure, tested in
tests/test_version_rules.py.

The three backends write their versions three ways:
  Spoolman  0.27.0             (and branch builds like fix-1246-backup-lock)
  FilaMan   v1.4.3             (and commit hashes)
  BamBuddy  1.2.5.7, 0.2.4b3, 1.3.0b1-daily.20261023
A version is a dotted number with an optional "v" in front and an optional
suffix; a suffix makes it a pre-release. Anything else (branches, hashes,
"latest", "daily", per-architecture tags) is not a version.
"""

import re

_VERSION_RE = re.compile(r"^v?(?P<core>\d+(?:\.\d+)+)(?P<suffix>[A-Za-z][0-9A-Za-z.\-]*|-[0-9A-Za-z.\-]+)?$")
# Per-architecture copies of a release, e.g. 1.2.5.7-arm64.
_ARCH_SUFFIX_RE = re.compile(r"-(amd64|arm64|armv7|arm)$")
_TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")


def normalize(tag: str) -> str:
    """The version without a leading "v": the form release names and image
    tags are compared in."""
    return tag[1:] if tag[:1] in ("v", "V") and tag[1:2].isdigit() else tag


def parse(tag: str) -> dict | None:
    if not isinstance(tag, str) or _ARCH_SUFFIX_RE.search(tag):
        return None
    match = _VERSION_RE.match(tag)
    if not match:
        return None
    suffix = (match.group("suffix") or "").lstrip("-")
    return {"core": tuple(int(p) for p in match.group("core").split(".")),
            "suffix": suffix, "prerelease": bool(suffix)}


def _suffix_key(suffix: str) -> tuple:
    # Numbers compare as numbers, words as words; (0, n) and (1, word) keep
    # the two from ever being compared with each other.
    return tuple((0, int(tok)) if tok.isdigit() else (1, tok.lower()) for tok in _TOKEN_RE.findall(suffix))


def sort_key(tag: str) -> tuple:
    """Orders versions; a release ranks above its own pre-releases
    (1.3.0 > 1.3.0b1). Only call it for tags parse() accepted."""
    v = parse(tag)
    core = v["core"] + (0,) * (6 - len(v["core"]))
    return (core, 0 if v["prerelease"] else 1, _suffix_key(v["suffix"]))


def versions(tags: list[str], include_prereleases: bool) -> list[str]:
    """The version tags among tags, newest first."""
    found = [t for t in tags if (v := parse(t)) and (include_prereleases or not v["prerelease"])]
    return sorted(set(found), key=sort_key, reverse=True)


def newer_than(tags: list[str], current: str, include_prereleases: bool) -> list[str]:
    """Versions newer than current, newest first. With a current that is not
    a version (a branch build someone set by hand) nothing counts as newer."""
    if parse(current) is None:
        return []
    floor = sort_key(current)
    return [t for t in versions(tags, include_prereleases) if sort_key(t) > floor]


def releases_between(releases: list[dict], current: str, target: str) -> list[dict]:
    """The release notes from just after current up to target, newest first.
    releases: dicts with a "tag" as GitHub names it."""
    if parse(current) is None or parse(target) is None:
        return []
    low, high = sort_key(current), sort_key(target)
    picked = [r for r in releases if parse(r["tag"]) and low < sort_key(r["tag"]) <= high]
    return sorted(picked, key=lambda r: sort_key(r["tag"]), reverse=True)
