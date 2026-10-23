"""The update flow with Docker, ghcr.io and the backups replaced by fakes:
what happens to the chosen version and the data when a step fails."""

import pytest

from spoolmanscale_pro import backend_updates as bu
from spoolmanscale_pro import settings
from spoolmanscale_pro.backends import backend_by_key
from spoolmanscale_pro.docker_compose import CommandResult
from spoolmanscale_pro.jobs import JobFailed

FILAMAN = backend_by_key("filaman")


class Progress:
    def __init__(self):
        self.steps, self.result = [], {}

    def step(self, code):
        self.steps.append(code)

    def warn(self, code):
        pass

    def set_result(self, **values):
        self.result.update(values)


@pytest.fixture
def fake(monkeypatch):
    calls = {"restored": [], "up_ok": True, "ready": True, "pull_ok": True}
    settings.update({"backend_versions": {}, "include_prereleases": False})
    monkeypatch.setattr(bu.release_sources, "image_tags", lambda image: ["v1.4.3", "v1.4.4", "v1.5.0"])
    monkeypatch.setattr(bu.release_sources, "releases", lambda repo: [{"tag": "v1.5.0"}, {"tag": "v1.4.4"}])
    monkeypatch.setattr(bu.docker_compose, "states", lambda: {"filaman": "running"})
    monkeypatch.setattr(bu.docker_compose, "pull", lambda key: CommandResult(calls["pull_ok"], ""))
    monkeypatch.setattr(bu.docker_compose, "up", lambda key: CommandResult(calls["up_ok"], ""))
    monkeypatch.setattr(bu.health, "wait_until_ready", lambda backend: calls["ready"])
    monkeypatch.setattr(bu.backups, "create", lambda backend, progress, reason: f"filaman_x_{reason}.tar")
    monkeypatch.setattr(bu.backups, "restore",
                        lambda backend, path, progress, keep_safety: calls["restored"].append(path.name))
    return calls


def test_check_lists_newer_versions_and_their_notes(fake):
    found = bu.check(FILAMAN)
    assert found["current"] == "v1.4.3" and found["default"] == "v1.4.3"
    assert found["newer"] == ["v1.5.0", "v1.4.4"]
    assert [n["tag"] for n in found["notes"]] == ["v1.5.0", "v1.4.4"]


def test_successful_update_keeps_the_new_version(fake):
    progress = Progress()
    bu.install(FILAMAN, "v1.5.0", progress)
    assert bu.current_version(FILAMAN) == "v1.5.0"
    assert progress.result == {"version": "v1.5.0", "backup": "filaman_x_before-update.tar"}
    assert fake["restored"] == []


def test_backend_that_does_not_come_up_gets_old_version_and_data_back(fake):
    fake["ready"] = False
    with pytest.raises(JobFailed) as e:
        bu.install(FILAMAN, "v1.5.0", Progress())
    assert e.value.code == "update_rolled_back"
    assert bu.current_version(FILAMAN) == "v1.4.3"
    assert fake["restored"] == ["filaman_x_before-update.tar"]


def test_failed_pull_changes_nothing(fake):
    fake["pull_ok"] = False
    with pytest.raises(JobFailed) as e:
        bu.install(FILAMAN, "v1.5.0", Progress())
    assert e.value.code == "pull_failed"
    assert bu.current_version(FILAMAN) == "v1.4.3"


def test_a_tag_that_is_not_offered_is_refused(fake):
    for bad in ("v9.9.9", "latest"):
        with pytest.raises(JobFailed) as e:
            bu.install(FILAMAN, bad, Progress())
        assert e.value.code == "unknown_version"
