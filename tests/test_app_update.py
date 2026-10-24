from spoolmanscale_pro.app_update import VERSION_RE, installable
from spoolmanscale_pro.version import APP_VERSION

RELEASES = [
    {"tag": "v2.1.0", "prerelease": False, "assets": ["spoolmanscale-pro-2.1.0.tar.gz", "spoolmanscale-pro-2.1.0.tar.gz.sha256"]},
    {"tag": "v2.1.0-beta.2", "prerelease": True, "assets": ["spoolmanscale-pro-2.1.0-beta.2.tar.gz"]},
    {"tag": "v2.0.1", "prerelease": False, "assets": []},
    {"tag": "v0.1.0", "prerelease": False, "assets": []},
]


def test_only_newer_releases_with_their_archive():
    assert [r["tag"] for r in installable(RELEASES, "2.0.0", False)] == ["v2.1.0"]
    assert [r["tag"] for r in installable(RELEASES, "2.0.0", True)] == ["v2.1.0", "v2.1.0-beta.2"]
    assert installable(RELEASES, "2.1.0", True) == []


def test_version_form():
    assert VERSION_RE.match(APP_VERSION)
    for bad in ("2.0", "2.0.0-rc1", "2.0.0;reboot", "../2.0.0"):
        assert not VERSION_RE.match(bad), bad
