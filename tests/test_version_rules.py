from spoolmanscale_pro import version_rules as vr

BAMBUDDY_TAGS = ["latest", "daily", "1.2.5.6", "1.2.5.7", "1.2.5.7-arm64", "0.2.4b3",
                 "1.3.0b1-daily.20261022", "1.3.0b1-daily.20261023", "spoolman-test_20260505"]


def test_what_counts_as_a_version():
    assert vr.parse("0.27.0") == {"core": (0, 27, 0), "suffix": "", "prerelease": False}
    assert vr.parse("v1.4.3")["core"] == (1, 4, 3)
    assert vr.parse("0.2.4b3")["prerelease"]
    assert vr.parse("1.3.0b1-daily.20261023")["suffix"] == "b1-daily.20261023"
    assert vr.parse("2.0.0-beta.2")["prerelease"]
    for not_a_version in ("latest", "daily", "fix-1246-backup-lock", "1.2.5.7-arm64",
                          "b62a0c22c0f5e24df08a4160edcfce2e89420d94", "7", None):
        assert vr.parse(not_a_version) is None, not_a_version


def test_order():
    assert vr.sort_key("1.2.5.7") > vr.sort_key("1.2.5.6")
    assert vr.sort_key("1.10.0") > vr.sort_key("1.9.9")
    assert vr.sort_key("1.3.0") > vr.sort_key("1.3.0b1")
    assert vr.sort_key("1.3.0b1") > vr.sort_key("1.2.5.7")
    assert vr.sort_key("1.3.0b2") > vr.sort_key("1.3.0b1-daily.20261023")
    assert vr.sort_key("1.3.0b1-daily.20261023") > vr.sort_key("1.3.0b1-daily.20261022")
    assert vr.sort_key("v1.4.3") == vr.sort_key("1.4.3")


def test_newer_than_with_and_without_prereleases():
    assert vr.newer_than(BAMBUDDY_TAGS, "1.2.5.6", False) == ["1.2.5.7"]
    assert vr.newer_than(BAMBUDDY_TAGS, "1.2.5.6", True) == [
        "1.3.0b1-daily.20261023", "1.3.0b1-daily.20261022", "1.2.5.7"]
    assert vr.newer_than(BAMBUDDY_TAGS, "1.2.5.7", False) == []
    assert vr.newer_than(BAMBUDDY_TAGS, "daily", True) == []


def test_releases_between():
    releases = [{"tag": t} for t in ("v1.4.3", "v1.4.2", "v1.4.1", "v1.4.0", "v1.3.9")]
    picked = vr.releases_between(releases, "v1.4.1", "v1.4.3")
    assert [r["tag"] for r in picked] == ["v1.4.3", "v1.4.2"]
    assert vr.releases_between(releases, "latest", "v1.4.3") == []


def test_normalize():
    assert vr.normalize("v1.4.3") == "1.4.3"
    assert vr.normalize("0.27.0") == "0.27.0"
    assert vr.normalize("very-old") == "very-old"


def test_display():
    assert vr.display("0.27.0") == "v0.27.0"
    assert vr.display("v1.4.3") == "v1.4.3"
    assert vr.display("1.3.0b1-daily.20261023") == "v1.3.0b1-daily.20261023"
    assert vr.display("daily@sha256:c087cbce438f4bccb59228e727d44294739bb5e202089fec2b50dbf2300b49d0") == "daily (c087cbc)"
    assert vr.display("fix-1246-backup-lock") == "fix-1246-backup-lock"
    assert vr.display("") == ""
