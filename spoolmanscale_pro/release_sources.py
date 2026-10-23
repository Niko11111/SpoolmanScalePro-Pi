"""Where new backend versions come from: the image tags on ghcr.io and the
release notes on GitHub. Both anonymous, both read-only.

Answers are kept for CACHE_S in memory: GitHub allows 60 anonymous requests
an hour per address, and a page reload must not use them up. A failure
comes back as SourceError with a code the page translates; a Pi without
internet is the normal case for it, not an exception.
"""

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

GHCR = "https://ghcr.io"
GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT_S = 10
CACHE_S = 15 * 60
TAGS_PER_PAGE = 1000
# ghcr pages its tag list; none of the three backends needs more than one
# page today, the limit only stops a loop.
MAX_TAG_PAGES = 5
RELEASES_PER_PAGE = 40
USER_AGENT = "SpoolmanScale-Pro"
_NEXT_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="next"')

_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()


class SourceError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _cached(key: str, fetch):
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_S:
            return hit[1]
    value = fetch()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def _get(url: str, headers: dict | None = None) -> tuple[bytes, str]:
    """Body and Link header of a GET, or SourceError."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as r:
            return r.read(), r.headers.get("Link", "")
    except urllib.error.HTTPError as e:
        log.warning("%s answered %d", url, e.code)
        raise SourceError("source_refused", f"HTTP {e.code}") from e
    except (urllib.error.URLError, OSError) as e:
        log.info("%s not reachable: %s", url, e)
        raise SourceError("no_internet", str(e)) from e


def _json(raw: bytes):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SourceError("source_bad_answer", str(e)) from e


def _fetch_tags(image: str) -> list[str]:
    token = _json(_get(f"{GHCR}/token?scope=repository:{image}:pull")[0]).get("token", "")
    url = f"{GHCR}/v2/{image}/tags/list?n={TAGS_PER_PAGE}"
    tags: list[str] = []
    for _ in range(MAX_TAG_PAGES):
        raw, link = _get(url, {"Authorization": f"Bearer {token}"})
        tags += _json(raw).get("tags") or []
        match = _NEXT_LINK_RE.search(link)
        if not match:
            break
        url = GHCR + match.group(1)
    return tags


def image_tags(image: str) -> list[str]:
    """Every tag of ghcr.io/<image>."""
    return _cached(f"tags:{image}", lambda: _fetch_tags(image))


def _fetch_releases(repo: str) -> list[dict]:
    raw, _ = _get(f"{GITHUB_API}/repos/{repo}/releases?per_page={RELEASES_PER_PAGE}",
                  {"Accept": "application/vnd.github+json"})
    rows = _json(raw)
    if not isinstance(rows, list):
        raise SourceError("source_bad_answer", "releases is not a list")
    return [{"tag": r.get("tag_name", ""), "name": r.get("name") or r.get("tag_name", ""),
             "body": r.get("body") or "", "prerelease": bool(r.get("prerelease")),
             "published": (r.get("published_at") or "")[:10], "url": r.get("html_url", ""),
             "assets": [a.get("name", "") for a in r.get("assets") or []]}
            for r in rows if not r.get("draft")]


def releases(repo: str) -> list[dict]:
    """The newest releases of github.com/<repo>, with their notes."""
    return _cached(f"releases:{repo}", lambda: _fetch_releases(repo))
