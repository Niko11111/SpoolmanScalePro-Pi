from spoolmanscale_pro import backend_status


def by_key(view):
    return {row["key"]: row for row in view["backends"]}


def test_merge_shows_version_always_and_spools_only_while_ready():
    details = {"spoolman": {"version": "v0.27.0", "spools": 24},
               "filaman": {"version": "v1.4.3", "spools": 7},
               "bambuddy": {"version": "daily (c087cbc)", "spools": None}}
    view = backend_status.merge({"spoolman": "running", "filaman": "running"}, "spoolman",
                                {"spoolman": True, "filaman": False}, {"spoolman": 180}, details)
    rows = by_key(view)
    assert rows["spoolman"]["version"] == "v0.27.0" and rows["spoolman"]["spools"] == 24
    assert rows["spoolman"]["ram_mb"] == 180 and rows["spoolman"]["active"]
    assert rows["filaman"]["spools"] is None  # still starting
    assert rows["bambuddy"]["state"] == "absent" and rows["bambuddy"]["version"] == "daily (c087cbc)"
    assert view["docker_ok"]


def test_merge_without_docker_or_details():
    view = backend_status.merge(None, None, {})
    assert not view["docker_ok"]
    assert all(row["version"] is None and row["spools"] is None for row in view["backends"])
