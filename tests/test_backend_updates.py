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
    # These tests are about the update, not about which default compose has now.
    monkeypatch.setattr(bu, "default_version", lambda backend: "v1.4.3")
    monkeypatch.setattr(bu.release_sources, "image_tags", lambda image: ["v1.4.3", "v1.4.4", "v1.5.0"])
    monkeypatch.setattr(bu.release_sources, "releases", lambda repo: [{"tag": "v1.5.0"}, {"tag": "v1.4.4"}])
    monkeypatch.setattr(bu.docker_compose, "states", lambda: {"filaman": "running"})
    monkeypatch.setattr(bu.docker_compose, "pull", lambda key: CommandResult(calls["pull_ok"], ""))
    monkeypatch.setattr(bu.docker_compose, "up", lambda key: CommandResult(calls["up_ok"], ""))
    monkeypatch.setattr(bu.health, "wait_until_ready", lambda backend: calls["ready"])
    calls["removed"] = []
    monkeypatch.setattr(bu.docker_compose, "image_of",
                        lambda key: "ghcr.io/x:" + bu.current_version(FILAMAN))
    monkeypatch.setattr(bu.docker_compose, "remove_image", lambda ref: calls["removed"].append(ref))
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
    assert fake["removed"] == ["ghcr.io/x:v1.4.3"]


def test_backend_that_does_not_come_up_gets_old_version_and_data_back(fake):
    fake["ready"] = False
    with pytest.raises(JobFailed) as e:
        bu.install(FILAMAN, "v1.5.0", Progress())
    assert e.value.code == "update_rolled_back"
    assert bu.current_version(FILAMAN) == "v1.4.3"
    assert fake["restored"] == ["filaman_x_before-update.tar"]
    assert fake["removed"] == ["ghcr.io/x:v1.5.0"]


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


def test_an_installed_backend_keeps_its_version_when_the_default_moves():
    defaults = {"filaman": "v2.0.0", "spoolman": "0.27.1", "bambuddy": "1.2.5.7"}
    installed = {"filaman": "v1.4.3", "spoolman": "0.27.1", "bambuddy": "1.2.5.6"}
    # Spoolman has the default; BamBuddy has a choice on record already.
    assert bu.versions_to_keep({"bambuddy": "1.2.5.6"}, installed, defaults) == {"filaman": "v1.4.3"}
    # Never started: no container, so the new default is what it gets.
    assert bu.versions_to_keep({}, {}, defaults) == {}
    # An image without a version in its name is left alone.
    assert bu.versions_to_keep({}, {"filaman": ""}, defaults) == {}


def test_only_a_backend_that_never_ran_picks_its_version():
    assert bu.is_first_start(None, False, False)
    assert not bu.is_first_start("v1.4.3", False, False)
    assert not bu.is_first_start(None, True, False)
    assert not bu.is_first_start(None, False, True)  # data left behind by a removed container


def first_start_world(monkeypatch, containers, volumes, tags=("v1.4.3", "v1.5.0", "v1.6.0-beta.1")):
    monkeypatch.setattr(bu, "default_version", lambda backend: "v1.4.3")
    monkeypatch.setattr(bu.docker_compose, "container_images", lambda: containers)
    monkeypatch.setattr(bu.docker_compose, "data_volumes", lambda: volumes)
    monkeypatch.setattr(bu.release_sources, "image_tags", lambda image: list(tags))
    settings.update({"backend_versions": {}})


def test_first_start_takes_the_newest_stable_release(monkeypatch):
    first_start_world(monkeypatch, containers={}, volumes=set())
    bu.choose_first_version(FILAMAN)
    assert settings.load()["backend_versions"] == {"filaman": "v1.5.0"}


def test_an_installed_backend_keeps_its_version(monkeypatch):
    first_start_world(monkeypatch, containers={"filaman": "ghcr.io/x:v1.4.3"}, volumes={"filaman-data"})
    bu.choose_first_version(FILAMAN)
    assert settings.load()["backend_versions"] == {}


def test_data_without_a_container_keeps_the_default(monkeypatch):
    first_start_world(monkeypatch, containers={}, volumes={"filaman-data"})
    bu.choose_first_version(FILAMAN)
    assert settings.load()["backend_versions"] == {}


def test_without_docker_or_ghcr_the_default_applies(monkeypatch):
    first_start_world(monkeypatch, containers=None, volumes=set())
    bu.choose_first_version(FILAMAN)
    assert settings.load()["backend_versions"] == {}

    def offline(image):
        raise bu.SourceError("source_unreachable", "offline")
    first_start_world(monkeypatch, containers={}, volumes=set())
    monkeypatch.setattr(bu.release_sources, "image_tags", offline)
    bu.choose_first_version(FILAMAN)
    assert settings.load()["backend_versions"] == {}
